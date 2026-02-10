import os
import sys
import time

from backend.config import Config

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)


import json
import sqlite3
from collections import deque
from typing import Deque, List, Optional

import numpy as np

from cache_layer.TopicState import TopicKey

from .history_node import HistoryEntry


class ConversationHistory:
    def __init__(
        self,
        max_size: int = 32,
        sim_threshold: float = 0.80,
        session_id: str = "",
        db_path: str = Config.DB_PATH,
        max_age_seconds: int = 3600,
    ):
        self.max_size = max_size
        self.sim_threshold = sim_threshold
        self.session_id = session_id
        self.db_path = db_path
        self.max_age_seconds = max_age_seconds
        self._entries: Deque[HistoryEntry] = deque(maxlen=max_size)

        self._init_db()
        self._load_from_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history_entries (
                session_id TEXT,
                topic_label TEXT,
                modality_filter TEXT,
                retrieval_policy TEXT,
                query_embedding BLOB,
                chunk_ids TEXT,
                timestamp REAL,
                PRIMARY KEY (session_id, topic_label, modality_filter, retrieval_policy)
            )
        """)
        conn.commit()
        conn.close()

    def _load_from_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """
            SELECT topic_label, modality_filter, retrieval_policy,
                   query_embedding, chunk_ids, timestamp
            FROM history_entries
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """,
            (self.session_id, self.max_size),
        )

        entries = []
        for row in cursor.fetchall():
            (
                topic_label,
                modality_filter,
                retrieval_policy,
                embedding_blob,
                chunk_ids_json,
                timestamp,
            ) = row

            key = TopicKey(
                topic_label=topic_label,
                modality_filter=modality_filter,
                retrieval_policy=retrieval_policy,
            )

            # Deserialize numpy array from blob
            query_embedding = np.frombuffer(embedding_blob, dtype=np.float32)
            chunk_ids = json.loads(chunk_ids_json)

            entry = HistoryEntry(
                topic_key=key,
                query_embedding=query_embedding,
                chunk_ids=chunk_ids,
                timestamp=timestamp,
            )
            entries.append(entry)

        conn.close()

        # Add to deque in reverse order (oldest first, newest last)
        for entry in reversed(entries):
            self._entries.append(entry)

    def _save_entry(self, entry: HistoryEntry):
        conn = sqlite3.connect(self.db_path)

        embedding_blob = entry.query_embedding.astype(np.float32).tobytes()

        conn.execute(
            """
            INSERT OR REPLACE INTO history_entries (
                session_id, topic_label, modality_filter, retrieval_policy,
                query_embedding, chunk_ids, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                self.session_id,
                entry.topic_key.topic_label,
                entry.topic_key.modality_filter,
                entry.topic_key.retrieval_policy,
                embedding_blob,
                json.dumps(entry.chunk_ids),
                entry.timestamp,
            ),
        )
        conn.commit()
        conn.close()

    def _clear_session_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "DELETE FROM history_entries WHERE session_id = ?",
            (self.session_id,),
        )
        conn.commit()
        conn.close()

    def find_similar(
        self,
        query_embedding: np.ndarray,
    ) -> Optional[List[str]]:
        """
        Return chunk_ids from the most recent semantically similar history entry,
        or None if no entry passes the similarity threshold.
        """
        self._evict_stale()

        if not self._entries:
            return None

        q = self._normalize(query_embedding)

        for entry in reversed(self._entries):
            e = self._normalize(entry.query_embedding)
            sim = float(np.dot(q, e))  # cosine similarity (both normalized)

            if sim >= self.sim_threshold:
                return entry.chunk_ids

        return None

    def add_or_update(
        self,
        topic_key: TopicKey,
        query_embedding: np.ndarray,
        chunk_ids: List[str],
    ) -> None:
        self._evict_stale()
        now = time.time()
        q = self._normalize(query_embedding)

        for i, entry in enumerate(self._entries):
            if entry.topic_key == topic_key:
                self._entries.remove(entry)
                new_entry = HistoryEntry(
                    topic_key=topic_key,
                    query_embedding=q,
                    chunk_ids=chunk_ids,
                    timestamp=now,
                )
                self._entries.append(new_entry)

                self._save_entry(new_entry)
                return

        new_entry = HistoryEntry(
            topic_key=topic_key,
            query_embedding=q,
            chunk_ids=chunk_ids,
            timestamp=now,
        )
        self._entries.append(new_entry)

        self._save_entry(new_entry)

    def clear(self) -> None:
        self._entries.clear()
        self._clear_session_db()

    def clear_session(self) -> None:
        self.clear()

    def size(self) -> int:
        return len(self._entries)

    def _evict_stale(self) -> None:
        cutoff = time.time() - self.max_age_seconds
        stale = [e for e in self._entries if e.timestamp < cutoff]
        if not stale:
            return
        for entry in stale:
            self._entries.remove(entry)
        # Bulk-delete from DB
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "DELETE FROM history_entries WHERE session_id = ? AND timestamp < ?",
            (self.session_id, cutoff),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def _normalize(vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        if norm == 0.0:
            return vec
        return vec / norm
