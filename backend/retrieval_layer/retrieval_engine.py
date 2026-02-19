import logging
import os
import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from cache_layer.cache import TopicCacheManager
from cache_layer.TopicState import TopicKey
from data_layer.chunkstore.Chunkstore import ChunkMetadataStore
from data_layer.ingest.storage.hnsw import HNSWIndex
from history_layer.history import ConversationHistory

logger = logging.getLogger("retrieval")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


@dataclass
class RetrievalResult:

    query: str
    chunk_ids: List[str]
    chunks_with_metadata: List[dict]
    source: str  # 'cache', 'history', or 'ann'
    reranked: bool
    validated: bool
    validation_retries: int = 0


@dataclass
class RAGResponse:

    query: str
    answer: str
    citations: List[dict]
    retrieval_source: str
    chunks_used: int
    success: bool
    error: Optional[str] = None
    expanded_query: Optional[str] = None


class QueryRouter:
    @staticmethod
    def infer_modality(query: str) -> str:
        q = query.lower()
        if any(w in q for w in ["image", "screenshot", "photo", "picture"]):
            return "image"
        if any(w in q for w in ["audio", "voice", "recording", "speech"]):
            return "audio"
        if any(w in q for w in ["pdf", "document", "doc", "book", "report"]):
            return "text"
        return "any"

    @staticmethod
    def infer_topic_label(query: str) -> str:
        q = query.lower().strip()
        q = re.sub(r"\s+", " ", q)
        return q

    @staticmethod
    def build_topic_key(query: str) -> TopicKey:
        topic_label = QueryRouter.infer_topic_label(query)
        modality = QueryRouter.infer_modality(query)
        retrieval_policy = "default"

        return TopicKey(
            topic_label=topic_label,
            modality_filter=modality,
            retrieval_policy=retrieval_policy,
        )


# Making this separate class so that when using mmap in C++ the integration and the multi threading can be handles in a more modular way
# Also this class can be extended in the future and also it introduces separation of concers and no GOD file concepts


class QueryProcessing:
    FILLER_PATTERNS = [
        r"^(i\s+want|i\s+need|can\s+you|please)\s+(find|get|give|show|search|look\s+for|retrieve)\s+(me\s+)?\s*(a\s+|the\s+|some\s+)?(file|document|info|information|data|content|text|article)s?\s*(which|that|about|on|regarding|related\s+to|with\s+information\s+(about|on))?\s*",
        r"^(find|get|give|show|search|look\s+for|retrieve)\s+(me\s+)?\s*(a\s+|the\s+|some\s+)?(file|document|info|information|data|content|text|article)s?\s*(which|that|about|on|regarding|related\s+to|with\s+information\s+(about|on))?\s*",
        r"^(tell\s+me|what\s+is|what\s+are|explain)\s+(about|regarding)?\s*",
    ]

    def __init__(self, conversation_memory, embedding_model=None):
        self.conversation_memory = conversation_memory
        self.embedding_model = embedding_model

    def _extract_query_intent(self, query: str) -> str:
        cleaned = query.strip()
        for pattern in self.FILLER_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
        if len(cleaned) < 3:
            return query
        return cleaned

    @staticmethod
    def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
        norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _expand_with_context(self, query: str, session_id: str) -> str:
        if not session_id or not self.conversation_memory:
            return query
        recent = self.conversation_memory.get_recent_queries(session_id, max_queries=3)
        if not recent or len(recent) <= 1:
            return query
        prior = recent[:-1]

        is_followup = any(
            w in query.lower()
            for w in ["more", "also", "else", "that", "this", "it", "they", "same"]
        )

        # Gate on semantic similarity — only expand if topically related
        if self.embedding_model is not None:
            q_emb = self.embedding_model.encode(query, normalize_embeddings=True)
            best_sim = max(
                self._cosine_sim(q_emb, self.embedding_model.encode(p, normalize_embeddings=True))
                for p in prior
            )
            if best_sim < 0.45 and not is_followup:
                logger.info(f"Query unrelated to history (sim={best_sim:.2f}), skipping expansion")
                return query

        short_words = len(query.split()) <= 4
        if short_words or is_followup:
            context = " | ".join(prior[-2:])
            expanded = f"{context} {query}"
            logger.info(f"Query expanded: '{query}' -> '{expanded}'")
            return expanded
        return query

    def preprocess_query(self, query: str, session_id: str = "") -> str:
        expanded = self._expand_with_context(query, session_id)
        intent = self._extract_query_intent(expanded)
        return intent


class RetrievalEngine(QueryProcessing):
    def __init__(
        self,
        cache: TopicCacheManager,
        index: HNSWIndex,
        embedding_model,
        history: ConversationHistory,
        ann_top_k: int = 5,
        history_enabled: bool = True,
        metadata_store: Optional[ChunkMetadataStore] = None,
        reranker=None,
        validator=None,
        generator=None,
        conversation_memory=None,
    ):
        self.cache = cache
        self.index = index
        self.embedding_model = embedding_model
        self.history = history
        self.ann_top_k = ann_top_k
        self.history_enabled = history_enabled
        self.metadata_store = metadata_store

        self._reranker = reranker
        self._validator = validator
        self._generator = generator
        self.conversation_memory = conversation_memory

    @property
    def reranker(self):
        if self._reranker is None:
            try:
                from reranking.reranker import CrossEncoderReranker

                self._reranker = CrossEncoderReranker()
                logger.info("Initialized cross-encoder reranker")
            except Exception as e:
                logger.warning(f"Could not initialize reranker: {e}")
        return self._reranker

    @property
    def validator(self):
        if self._validator is None:
            try:
                from validation_layer.validator import RetrievalValidator

                self._validator = RetrievalValidator(
                    embedding_model=self.embedding_model
                )
                logger.info("Initialized retrieval validator")
            except Exception as e:
                logger.warning(f"Could not initialize validator: {e}")
        return self._validator

    @property
    def generator(self):
        if self._generator is None:
            try:
                from generation_layer.generator import AnswerGenerator

                self._generator = AnswerGenerator()
                logger.info("Initialized answer generator")
            except Exception as e:
                logger.warning(f"Could not initialize generator: {e}")
        return self._generator

    def retrieve(self, query: str) -> List[str]:
        """
        Basic retrieval returning chunk IDs.
        Uses cache -> history -> ANN fallback chain.
        """
        key = QueryRouter.build_topic_key(query)

        state = self.cache.lookup(key)
        if state is not None:
            logger.info(
                f"CACHE HIT: {len(state.cached_chunk_ids)} chunks for '{key.topic_label}'"
            )
            query_vec = self._embed_query(query)
            self.history.add_or_update(key, query_vec, state.cached_chunk_ids)
            return state.cached_chunk_ids

        query_vec = self._embed_query(query)

        if self.history_enabled:
            reused = self.history.find_similar(query_vec)
            if reused is not None:
                logger.info("HISTORY HIT")
                self.cache.insert_new(key, cached_chunk_ids=reused)
                self.history.add_or_update(key, query_vec, reused)
                return reused

        logger.info("ANN FALLBACK")
        chunk_ids = self._ann_search(query_vec)

        self.cache.insert_new(key, cached_chunk_ids=chunk_ids)
        self.history.add_or_update(key, query_vec, chunk_ids)
        return chunk_ids

    def retrieve_with_metadata(self, query: str) -> List[dict]:
        chunk_ids = self.retrieve(query)
        if self.metadata_store is None:
            return [{"chunk_id": cid} for cid in chunk_ids]
        return self.metadata_store.get_by_ids(chunk_ids)

    def retrieve_enhanced(self, query: str) -> RetrievalResult:
        key = QueryRouter.build_topic_key(query)
        source = "ann"

        # Embed query ONCE — reused for history, validation, lightweight reranking
        query_vec = self._embed_query(query)

        state = self.cache.lookup(key)
        if state is not None:
            logger.info(
                f"CACHE HIT: {len(state.cached_chunk_ids)} cached chunks for '{key.topic_label}'"
            )
            source = "cache"
            chunk_ids = state.cached_chunk_ids
        else:
            if self.history_enabled:
                reused = self.history.find_similar(query_vec)
                if reused is not None:
                    logger.info("HISTORY HIT")
                    source = "history"
                    chunk_ids = reused
                else:
                    logger.info("ANN FALLBACK")
                    chunk_ids = self._ann_search(query_vec, k=self.ann_top_k * 2)
            else:
                chunk_ids = self._ann_search(query_vec, k=self.ann_top_k * 2)

        chunks_with_text = self._get_chunks_with_text(chunk_ids)

        reranked = False
        if chunks_with_text:
            try:
                if source == "ann" and self.reranker:
                    rerank_results = self.reranker.rerank(
                        query, chunks_with_text, text_key="chunk_text"
                    )
                    chunks_with_text = [r.metadata for r in rerank_results]
                    reranked = True
                    logger.info(
                        f"Cross-encoder reranked to {len(chunks_with_text)} chunks"
                    )
                else:
                    from reranking.reranker import LightweightReranker

                    light = LightweightReranker(
                        embedding_model=self.embedding_model,
                        top_k=self.ann_top_k,
                    )
                    chunks_with_text = light.rerank(query_vec, chunks_with_text)
                    reranked = True
                    logger.info(
                        f"Lightweight reranked to {len(chunks_with_text)} chunks"
                    )

                chunk_ids = [c["chunk_id"] for c in chunks_with_text]
            except Exception as e:
                logger.warning(f"Reranking failed: {e}")

        validated = False
        validation_retries = 0
        if self.validator and chunks_with_text:
            try:
                result, retries = self.validator.validate_with_retry(
                    query,
                    retrieval_fn=lambda q: self._retrieve_fresh(q),
                    initial_chunks=chunks_with_text,
                    query_embedding=query_vec,
                )
                chunks_with_text = result.validated_chunks
                chunk_ids = [c["chunk_id"] for c in chunks_with_text]
                validated = True
                validation_retries = retries
                logger.info(
                    f"Validation: {len(chunk_ids)} valid chunks, {retries} retries"
                )
            except Exception as e:
                logger.warning(f"Validation failed: {e}")

        if chunk_ids:
            self.cache.insert_new(key, cached_chunk_ids=chunk_ids)
            self.history.add_or_update(key, query_vec, chunk_ids)

        return RetrievalResult(
            query=query,
            chunk_ids=chunk_ids,
            chunks_with_metadata=chunks_with_text,
            source=source,
            reranked=reranked,
            validated=validated,
            validation_retries=validation_retries,
        )

    def retrieve_and_generate(
        self, query, intent_query: str, session_id: str = ""
    ) -> RAGResponse:

        retrieval_result = self.retrieve_enhanced(intent_query)

        if not retrieval_result.chunks_with_metadata:
            return RAGResponse(
                query=query,
                answer="I couldn't find any relevant information to answer your question.",
                citations=[],
                retrieval_source=retrieval_result.source,
                chunks_used=0,
                success=False,
                error="No chunks retrieved",
                expanded_query=intent_query if intent_query != query else None,
            )

        # 2) Generate answer with citations
        if self.generator is None:
            # Fallback: return chunk summaries
            chunks_text = "\n\n---\n\n".join(
                [
                    f"[{i+1}] {c.get('chunk_text', '')[:200]}..."
                    for i, c in enumerate(retrieval_result.chunks_with_metadata[:5])
                ]
            )
            return RAGResponse(
                query=query,
                answer=f"Found {len(retrieval_result.chunks_with_metadata)} relevant chunks:\n\n{chunks_text}",
                citations=[],
                retrieval_source=retrieval_result.source,
                chunks_used=len(retrieval_result.chunks_with_metadata),
                success=True,
            )

        try:

            effective_query = self._expand_with_context(query, session_id)
            gen_result = self.generator.generate(
                query=effective_query,
                chunks=retrieval_result.chunks_with_metadata,
                conversation_context=self._get_conversation_context(session_id),
            )

            # Convert citations to dicts
            citations = [
                {
                    "id": c.citation_id,
                    "chunk_id": c.chunk_id,
                    "source_path": c.source_path,
                    "chunk_text": c.chunk_text,
                    "start_offset": c.start_offset,
                    "end_offset": c.end_offset,
                }
                for c in gen_result.citations
            ]

            return RAGResponse(
                query=query,
                answer=gen_result.answer,
                citations=citations,
                retrieval_source=retrieval_result.source,
                chunks_used=len(retrieval_result.chunks_with_metadata),
                success=gen_result.success,
                error=gen_result.error,
                expanded_query=intent_query if intent_query != query else None,
            )

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return RAGResponse(
                query=query,
                answer=f"Error generating answer: {e}",
                citations=[],
                retrieval_source=retrieval_result.source,
                chunks_used=len(retrieval_result.chunks_with_metadata),
                success=False,
                error=str(e),
            )

    def _expand_with_context(self, query: str, session_id: str) -> str:
        if not session_id or not self.conversation_memory:
            return query
        recent = self.conversation_memory.get_recent_queries(session_id, max_queries=3)
        if not recent or len(recent) <= 1:
            return query
        prior = recent[:-1]

        is_followup = any(
            w in query.lower()
            for w in ["more", "also", "else", "that", "this", "it", "they", "same"]
        )

        # Gate on semantic similarity — skip expansion for unrelated queries
        if self.embedding_model is not None:
            q_emb = self._embed_query(query)
            best_sim = max(
                float(np.dot(q_emb, self._embed_query(p)))
                for p in prior
            )
            if best_sim < 0.45 and not is_followup:
                logger.info(f"Query unrelated to history (sim={best_sim:.2f}), skipping expansion")
                return query

        short_words = len(query.split()) <= 4
        if short_words or is_followup:
            context = " | ".join(prior[-2:])
            expanded = f"{context} {query}"
            logger.info(f"Query expanded: '{query}' -> '{expanded}'")
            return expanded
        return query

    def _get_conversation_context(self, session_id: str) -> list:
        if not session_id or not self.conversation_memory:
            return []
        return self.conversation_memory.get_context(session_id, max_turns=4)

    def _embed_query(self, query: str) -> np.ndarray:
        vec = self.embedding_model.encode(
            query,
            normalize_embeddings=True,
        )
        return np.asarray(vec, dtype="float32")

    def _ann_search(self, query_vector: np.ndarray, k: int = 0) -> List[str]:
        k = k or self.ann_top_k
        return self.index.search(query_vector, k=k)

    def _get_chunks_with_text(self, chunk_ids: List[str]) -> List[dict]:
        """Get chunks with their text content from metadata store."""
        if not self.metadata_store:
            return [{"chunk_id": cid} for cid in chunk_ids]

        metadata = self.metadata_store.get_by_ids(chunk_ids)

        # Check each chunk for text from DB. Do NOT fall back to reading
        # source files — offsets refer to normalised text, not raw PDFs.
        for meta in metadata:
            if meta.get("chunk_text", "").strip():
                continue  # Already have text from database

            # Text missing — flag clearly so the LLM doesn't hallucinate
            source_path = meta.get("source_path", "unknown")
            logger.warning(
                f"Chunk {meta.get('chunk_id', '?')[:16]} has no stored text. "
                f"Run 'python backfill_chunks.py' or re-ingest {source_path}"
            )
            meta["chunk_text"] = ""

        # Filter out chunks with no usable text
        return [m for m in metadata if m.get("chunk_text", "").strip()]

    def _retrieve_fresh(self, query: str) -> List[dict]:
        query_vec = self._embed_query(query)
        chunk_ids = self._ann_search(query_vec, k=self.ann_top_k * 2)
        return self._get_chunks_with_text(chunk_ids)
