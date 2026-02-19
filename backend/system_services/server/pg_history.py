import json
import os
import sys
import time
from typing import List, Optional
from uuid import UUID

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
project_dir = os.path.dirname(parent_dir)
sys.path.append(project_dir)

import numpy as np

from data_models.history import HistorySession, HistoryTurn
from data_models.session import SessionLocal


class PgConversationHistory:
    """
    The existing cache_topics schema lacks a chunk_ids column, so full
    semantic-history-based retrieval (store embedding + chunk_ids per query)
    cannot be mapped 1:1 onto the current PostgreSQL tables. Instead this
    class keeps an in-memory deque per user scoped by their history_sessions
    and always falls through to ANN search. This matches the TUI behaviour
    when history is empty.
    """

    def __init__(self, sim_threshold: float = 0.90, max_age_seconds: int = 3600):
        self.sim_threshold = sim_threshold
        self.max_age_seconds = max_age_seconds
        self._user_entries: dict = {}

    def find_similar(self, user_id: UUID, query_embedding: np.ndarray) -> Optional[List[str]]:
        entries = self._user_entries.get(str(user_id), [])
        if not entries:
            return None

        q = self._normalize(query_embedding)
        cutoff = time.time() - self.max_age_seconds

        for entry in reversed(entries):
            if entry["timestamp"] < cutoff:
                continue
            e = self._normalize(entry["embedding"])
            sim = float(np.dot(q, e))
            if sim >= self.sim_threshold:
                return entry["chunk_ids"]

        return None

    def add_or_update(
        self,
        user_id: UUID,
        topic_label: str,
        query_embedding: np.ndarray,
        chunk_ids: List[str],
    ):
        uid = str(user_id)
        if uid not in self._user_entries:
            self._user_entries[uid] = []

        entries = self._user_entries[uid]

        for i, entry in enumerate(entries):
            if entry["topic"] == topic_label:
                entries[i] = {
                    "topic": topic_label,
                    "embedding": query_embedding,
                    "chunk_ids": chunk_ids,
                    "timestamp": time.time(),
                }
                return

        entries.append({
            "topic": topic_label,
            "embedding": query_embedding,
            "chunk_ids": chunk_ids,
            "timestamp": time.time(),
        })

        if len(entries) > 32:
            self._user_entries[uid] = entries[-32:]

    @staticmethod
    def _normalize(vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        if norm == 0.0:
            return vec
        return vec / norm
