import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import re
from typing import List, Optional

import numpy as np

from cache_layer.cache import TopicCacheManager
from cache_layer.TopicState import TopicKey
from data_layer.ingest.storage.hnsw import HNSWIndex


class QueryRouter:
    """
    Very simple, rule-based router for v1.
    Later this can be replaced by a classifier/intent model.
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
        """
        For v1: normalize and lightly clean.
        Keep it simple and deterministic.
        """
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
    - ANN fallback
    - Cache insertion
    """

    def __init__(
        self,
        cache: TopicCacheManager,
        index: HNSWIndex,
        embedding_model,
        ann_top_k: int = 5,
    ):
        self.cache = cache
        self.index = index
        self.embedding_model = embedding_model
        self.ann_top_k = ann_top_k

    def retrieve(self, query: str) -> List[str]:
        """
        Returns a list of chunk_ids.
        """
        key = QueryRouter.build_topic_key(query)

        state = self.cache.lookup(key)
        if state is not None:
            return state.cached_chunk_ids

        chunk_ids = self._ann_search(query)

        self.cache.insert_new(key, cached_chunk_ids=chunk_ids)

        return chunk_ids

    def _ann_search(self, query: str) -> List[str]:
        """
        Embed the query and search FAISS HNSW.
        """
        # Encode query
        vector = self.embedding_model.encode(
            query,
            normalize_embeddings=True,
        )

        # Search ANN
        results = self.index.search(vector, k=self.ann_top_k)

        return results
