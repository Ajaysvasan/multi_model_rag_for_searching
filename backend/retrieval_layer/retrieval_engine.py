"""
Enhanced Retrieval Engine.

Orchestrates the full RAG pipeline:
Query → Cache/History → ANN → Reranking → Validation → Generation

Integrates:
- Topic-based cache (3-tier LRU with persistence)
- Session history with similarity matching
- Cross-encoder reranking
- Retrieval validation with re-retrieval
- Answer generation with citations
"""

import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from cache_layer.cache import TopicCacheManager
from cache_layer.TopicState import TopicKey
from config import Config
from data_layer.chunkstore.Chunkstore import ChunkMetadataStore
from data_layer.ingest.storage.hnsw import HNSWIndex
from history_layer.history import ConversationHistory

# -------------------------
# Logging setup
# -------------------------
logger = logging.getLogger("retrieval")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


@dataclass
class RetrievalResult:
    """Complete result from retrieval pipeline."""
    query: str
    chunk_ids: List[str]
    chunks_with_metadata: List[dict]
    source: str  # 'cache', 'history', or 'ann'
    reranked: bool
    validated: bool
    validation_retries: int = 0


@dataclass 
class RAGResponse:
    """Full RAG response with answer and citations."""
    query: str
    answer: str
    citations: List[dict]
    retrieval_source: str
    chunks_used: int
    success: bool
    error: Optional[str] = None


class QueryRouter:
    """
    Simple, rule-based router for v1.
    """

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


class RetrievalEngine:
    """
    Enhanced RAG retrieval engine.
    
    Orchestrates:
    - Query -> TopicKey
    - Cache lookup
    - History fallback (per session)
    - ANN fallback
    - Reranking (cross-encoder)
    - Validation (with re-retrieval)
    - Answer generation (with citations)
    - Cache + History update
    """

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
    ):
        self.cache = cache
        self.index = index
        self.embedding_model = embedding_model
        self.history = history
        self.ann_top_k = ann_top_k
        self.history_enabled = history_enabled
        self.metadata_store = metadata_store
        
        # New layers (lazy loaded if not provided)
        self._reranker = reranker
        self._validator = validator
        self._generator = generator
    
    # -------------------------
    # Lazy initialization
    # -------------------------
    
    @property
    def reranker(self):
        """Lazy load reranker."""
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
        """Lazy load validator."""
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
        """Lazy load generator."""
        if self._generator is None:
            try:
                from generation_layer.generator import AnswerGenerator
                self._generator = AnswerGenerator()
                logger.info("Initialized answer generator")
            except Exception as e:
                logger.warning(f"Could not initialize generator: {e}")
        return self._generator

    # -------------------------
    # Public API
    # -------------------------

    def retrieve(self, query: str) -> List[str]:
        """
        Basic retrieval returning chunk IDs.
        Uses cache -> history -> ANN fallback chain.
        """
        key = QueryRouter.build_topic_key(query)

        # 1) Cache lookup
        state = self.cache.lookup(key)
        if state is not None:
            logger.info(f"CACHE HIT: {len(state.cached_chunk_ids)} chunks for '{key.topic_label}'")
            query_vec = self._embed_query(query)
            self.history.add_or_update(key, query_vec, state.cached_chunk_ids)
            return state.cached_chunk_ids

        # 2) Embed once (used for history + ANN)
        query_vec = self._embed_query(query)

        # 3) History lookup
        if self.history_enabled:
            reused = self.history.find_similar(query_vec)
            if reused is not None:
                logger.info("HISTORY HIT")
                self.cache.insert_new(key, cached_chunk_ids=reused)
                self.history.add_or_update(key, query_vec, reused)
                return reused

        # 4) ANN search
        logger.info("ANN FALLBACK")
        chunk_ids = self._ann_search(query_vec)

        # 5) Update cache + history
        self.cache.insert_new(key, cached_chunk_ids=chunk_ids)
        self.history.add_or_update(key, query_vec, chunk_ids)
        return chunk_ids

    def retrieve_with_metadata(self, query: str) -> List[dict]:
        """Retrieve chunks with metadata."""
        chunk_ids = self.retrieve(query)
        if self.metadata_store is None:
            return [{"chunk_id": cid} for cid in chunk_ids]
        return self.metadata_store.get_by_ids(chunk_ids)
    
    def retrieve_enhanced(self, query: str) -> RetrievalResult:
        """
        Enhanced retrieval with reranking and validation.
        
        Pipeline: Cache/History/ANN -> Get Text -> Rerank -> Validate
        
        Returns:
            RetrievalResult with full metadata
        """
        key = QueryRouter.build_topic_key(query)
        source = "ann"
        
        # 1) Try cache first
        state = self.cache.lookup(key)
        if state is not None:
            logger.info(f"CACHE HIT: {len(state.cached_chunk_ids)} cached chunks for '{key.topic_label}'")
            source = "cache"
            chunk_ids = state.cached_chunk_ids
        else:
            # 2) Embed query for history + ANN
            query_vec = self._embed_query(query)
            
            # 3) Try history
            if self.history_enabled:
                reused = self.history.find_similar(query_vec)
                if reused is not None:
                    logger.info("HISTORY HIT")
                    source = "history"
                    chunk_ids = reused
                else:
                    # 4) ANN fallback
                    logger.info("ANN FALLBACK")
                    # Fetch more candidates for reranking
                    chunk_ids = self._ann_search(query_vec, k=self.ann_top_k * 2)
            else:
                chunk_ids = self._ann_search(query_vec, k=self.ann_top_k * 2)
        
        # 5) Get metadata and text for chunks
        chunks_with_text = self._get_chunks_with_text(chunk_ids)
        
        # 6) Rerank if available
        reranked = False
        if self.reranker and source == "ann":
            try:
                rerank_results = self.reranker.rerank(query, chunks_with_text, text_key="chunk_text")
                chunks_with_text = [r.metadata for r in rerank_results]
                
                # Update chunk_ids to reranked order
                chunk_ids = [c["chunk_id"] for c in chunks_with_text]
                reranked = True
                logger.info(f"Reranked to {len(chunk_ids)} chunks")
            except Exception as e:
                logger.warning(f"Reranking failed: {e}")
        
        # 7) Validate if available
        validated = False
        validation_retries = 0
        if self.validator and source == "ann":
            try:
                result, retries = self.validator.validate_with_retry(
                    query,
                    retrieval_fn=lambda q: self._retrieve_fresh(q),
                    initial_chunks=chunks_with_text,
                    query_embedding=self._embed_query(query),
                )
                chunks_with_text = result.validated_chunks
                chunk_ids = [c["chunk_id"] for c in chunks_with_text]
                validated = True
                validation_retries = retries
                logger.info(f"Validation complete: {len(chunk_ids)} valid chunks, {retries} retries")
            except Exception as e:
                logger.warning(f"Validation failed: {e}")
        
        # 8) Update cache + history with final results
        if chunk_ids and source == "ann":
            query_vec = self._embed_query(query)
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
    
    def retrieve_and_generate(self, query: str) -> RAGResponse:
        """
        Full RAG pipeline: retrieve + rerank + validate + generate answer.
        
        Returns:
            RAGResponse with answer and citations
        """
        # 1) Enhanced retrieval
        retrieval_result = self.retrieve_enhanced(query)
        
        if not retrieval_result.chunks_with_metadata:
            return RAGResponse(
                query=query,
                answer="I couldn't find any relevant information to answer your question.",
                citations=[],
                retrieval_source=retrieval_result.source,
                chunks_used=0,
                success=False,
                error="No chunks retrieved",
            )
        
        # 2) Generate answer with citations
        if self.generator is None:
            # Fallback: return chunk summaries
            chunks_text = "\n\n---\n\n".join([
                f"[{i+1}] {c.get('chunk_text', '')[:200]}..."
                for i, c in enumerate(retrieval_result.chunks_with_metadata[:5])
            ])
            return RAGResponse(
                query=query,
                answer=f"Found {len(retrieval_result.chunks_with_metadata)} relevant chunks:\n\n{chunks_text}",
                citations=[],
                retrieval_source=retrieval_result.source,
                chunks_used=len(retrieval_result.chunks_with_metadata),
                success=True,
            )
        
        try:
            gen_result = self.generator.generate(
                query=query,
                chunks=retrieval_result.chunks_with_metadata,
            )
            
            # Convert citations to dicts
            citations = [
                {
                    "id": c.citation_id,
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

    # -------------------------
    # Internal helpers
    # -------------------------

    def _embed_query(self, query: str) -> np.ndarray:
        vec = self.embedding_model.encode(
            query,
            normalize_embeddings=True,
        )
        return np.asarray(vec, dtype="float32")

    def _ann_search(self, query_vector: np.ndarray, k: int = None) -> List[str]:
        k = k or self.ann_top_k
        return self.index.search(query_vector, k=k)
    
    def _get_chunks_with_text(self, chunk_ids: List[str]) -> List[dict]:
        """Get chunks with their text content from metadata store."""
        if not self.metadata_store:
            return [{"chunk_id": cid} for cid in chunk_ids]
        
        metadata = self.metadata_store.get_by_ids(chunk_ids)
        
        # Check each chunk for text - prefer DB stored text, fallback to file
        for meta in metadata:
            # First, check if we have text stored in DB
            if meta.get("chunk_text"):
                continue  # Already have text from database
            
            # Fallback: try to load from source file (for old ingestions)
            try:
                source_path = meta.get("source_path")
                start_offset = meta.get("start_offset", 0)
                end_offset = meta.get("end_offset", 0)
                
                if source_path and os.path.exists(source_path):
                    with open(source_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                        if start_offset < len(content) and end_offset <= len(content):
                            meta["chunk_text"] = content[start_offset:end_offset]
                        else:
                            meta["chunk_text"] = f"[Offset out of range for {source_path}]"
                else:
                    meta["chunk_text"] = f"[Source file not found: {source_path}]"
            except Exception as e:
                logger.warning(f"Could not load chunk text: {e}")
                meta["chunk_text"] = "[Text unavailable]"
        
        return metadata
    
    def _retrieve_fresh(self, query: str) -> List[dict]:
        """Fresh ANN retrieval for validation retry."""
        query_vec = self._embed_query(query)
        chunk_ids = self._ann_search(query_vec, k=self.ann_top_k * 2)
        return self._get_chunks_with_text(chunk_ids)
