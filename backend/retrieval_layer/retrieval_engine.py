import logging
import os
import re
import sys
import time
from typing import List, Optional

import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from cache_layer.cache import TopicCacheManager
from cache_layer.TopicState import TopicKey
from data_layer.ingest.storage.hnsw import HNSWIndex
from data_layer.chunkstore.Chunkstore import ChunkMetadataStore
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
    Orchestrates:
    - Query -> TopicKey
    - Cache lookup
    - History fallback (per session)
    - ANN fallback
    - Cache + History update
    - Optional metadata join
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
    ):
        self.cache = cache
        self.index = index
        self.embedding_model = embedding_model
        self.history = history
        self.ann_top_k = ann_top_k
        self.history_enabled = history_enabled
        self.metadata_store = metadata_store

    # -------------------------
    # Public API
    # -------------------------

    def retrieve(self, query: str) -> List[str]:
        key = QueryRouter.build_topic_key(query)

        # 1) Cache
        state = self.cache.lookup(key)
        if state is not None:
            logger.info("CACHE HIT")
            query_vec = self._embed_query(query)
            self.history.add_or_update(key, query_vec, state.cached_chunk_ids)
            return state.cached_chunk_ids

        # 2) Embed once (used for history + ANN)
        query_vec = self._embed_query(query)

        # 3) History
        if self.history_enabled:
            reused = self.history.find_similar(query_vec)
            if reused is not None:
                logger.info("HISTORY HIT")
                self.cache.insert_new(key, cached_chunk_ids=reused)
                self.history.add_or_update(key, query_vec, reused)
                return reused

        # 4) ANN
        logger.info("ANN FALLBACK")
        chunk_ids = self._ann_search(query_vec)

        # 5) Update cache + history
        self.cache.insert_new(key, cached_chunk_ids=chunk_ids)
        self.history.add_or_update(key, query_vec, chunk_ids)
        return chunk_ids

    def retrieve_with_metadata(self, query: str):
        chunk_ids = self.retrieve(query)
        if self.metadata_store is None:
            return chunk_ids
        return self.metadata_store.get_by_ids(chunk_ids)

    # -------------------------
    # Internal helpers
    # -------------------------

    def _embed_query(self, query: str) -> np.ndarray:
        vec = self.embedding_model.encode(
            query,
            normalize_embeddings=True,
        )
        return np.asarray(vec, dtype="float32")

    def _ann_search(self, query_vector: np.ndarray) -> List[str]:
        return self.index.search(query_vector, k=self.ann_top_k)
