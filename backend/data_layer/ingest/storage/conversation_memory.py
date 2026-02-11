import os
import sqlite3
import time
from typing import List, Optional


class ConversationMemory:

    def __init__(self, db_path: str, max_turns: int = 10):
        self.db_path = db_path
        self.max_turns = max_turns
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._create_tables()

    def _create_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL
            );
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id, timestamp);"
        )
        self._conn.commit()

    def add_turn(self, session_id: str, role: str, content: str):
        self._conn.execute(
            "INSERT INTO turns (session_id, role, content, timestamp) VALUES (?, ?, ?, ?);",
            (session_id, role, content, time.time()),
        )
        self._conn.commit()
        self._trim(session_id)

    def get_context(self, session_id: str, max_turns: Optional[int] = None) -> List[dict]:
        limit = max_turns or self.max_turns
        cur = self._conn.execute(
            "SELECT role, content FROM turns WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?;",
            (session_id, limit),
        )
        rows = cur.fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    def get_recent_queries(self, session_id: str, max_queries: int = 3) -> List[str]:
        cur = self._conn.execute(
            "SELECT content FROM turns WHERE session_id = ? AND role = 'user' ORDER BY timestamp DESC LIMIT ?;",
            (session_id, max_queries),
        )
        return [r[0] for r in reversed(cur.fetchall())]

    def _trim(self, session_id: str):
        count = self._conn.execute(
            "SELECT COUNT(*) FROM turns WHERE session_id = ?;", (session_id,)
        ).fetchone()[0]

        if count > self.max_turns * 2:
            self._conn.execute(
                """DELETE FROM turns WHERE id IN (
                    SELECT id FROM turns WHERE session_id = ?
                    ORDER BY timestamp ASC LIMIT ?
                );""",
                (session_id, count - self.max_turns),
            )
            self._conn.commit()

    def clear_session(self, session_id: str):
        self._conn.execute("DELETE FROM turns WHERE session_id = ?;", (session_id,))
        self._conn.commit()

    def close(self):
        self._conn.close()
