import os
import sys
import time

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
    """
    Per-session, bounded semantic history for retrieval reuse.
    """

    def __init__(
        self, max_size: int = 32, sim_threshold: float = 0.80, session_id: str = "", db_path: str = "data/index/cache_history.db"
    ):
        self.max_size = max_size
        self.sim_threshold = sim_threshold
        self.session_id = session_id
        self.db_path = db_path
        self._entries: Deque[HistoryEntry] = deque(maxlen=max_size)
        
        # Initialize database and load existing history
        self._init_db()
        self._load_from_db()

    def _init_db(self):
        """Initialize database connection and create history table if needed."""
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
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
        """
        )
        conn.commit()
        conn.close()

    def _load_from_db(self):
        """Load history entries for this session from database."""
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
        """Save or update a single history entry in the database."""
        conn = sqlite3.connect(self.db_path)
        
        # Serialize numpy array to blob
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
        """Clear all history entries for this session from the database."""
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
        """
        Add a new history entry. If an entry with the same topic_key exists,
        refresh it and move it to the most recent position.
        """
        now = time.time()
        q = self._normalize(query_embedding)

        # Check if entry already exists
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
                
                # Persist to database
                self._save_entry(new_entry)
                return

        # New entry
        new_entry = HistoryEntry(
            topic_key=topic_key,
            query_embedding=q,
            chunk_ids=chunk_ids,
            timestamp=now,
        )
        self._entries.append(new_entry)
        
        # Persist to database
        self._save_entry(new_entry)

    def clear(self) -> None:
        """Clear history (e.g., on session end)."""
        self._entries.clear()
        self._clear_session_db()

    def size(self) -> int:
        return len(self._entries)

    @staticmethod
    def _normalize(vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        if norm == 0.0:
            return vec
        return vec / norm
