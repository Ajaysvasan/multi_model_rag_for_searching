import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class ChunkMetadataStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._create_tables()

    def close(self) -> None:
        self._conn.close()

    def _create_tables(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,

                source_path TEXT NOT NULL,
                modality TEXT NOT NULL,

                chunk_index INTEGER NOT NULL,

                start_offset INTEGER NOT NULL,
                end_offset INTEGER NOT NULL,

                chunk_version TEXT NOT NULL,
                normalization_version TEXT NOT NULL
            );
            """)

        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chunks_modality ON chunks(modality);"
        )

        self._conn.commit()

    def insert_many(self, rows: Iterable[Dict[str, Any]]) -> None:
        """
        Insert many chunk metadata rows.

        Each row must contain keys:
        - chunk_id
        - document_id
        - source_path
        - modality
        - chunk_index
        - start_offset
        - end_offset
        - chunk_version
        - normalization_version

        Duplicate chunk_ids are ignored (idempotent ingestion).
        """

        sql = """
        INSERT OR IGNORE INTO chunks (
            chunk_id,
            document_id,
            source_path,
            modality,
            chunk_index,
            start_offset,
            end_offset,
            chunk_version,
            normalization_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """

        values = []
        for r in rows:
            values.append(
                (
                    r["chunk_id"],
                    r["document_id"],
                    r["source_path"],
                    r["modality"],
                    int(r["chunk_index"]),
                    int(r["start_offset"]),
                    int(r["end_offset"]),
                    r["chunk_version"],
                    r["normalization_version"],
                )
            )

        with self._conn:
            self._conn.executemany(sql, values)

    def get_by_ids(self, chunk_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch metadata rows for the given chunk_ids.
        Returns a list of dicts. Missing IDs are silently skipped.
        """

        if not chunk_ids:
            return []

        placeholders = ",".join("?" for _ in chunk_ids)
        sql = f"""
        SELECT
            chunk_id,
            document_id,
            source_path,
            modality,
            chunk_index,
            start_offset,
            end_offset,
            chunk_version,
            normalization_version
        FROM chunks
        WHERE chunk_id IN ({placeholders});
        """

        cur = self._conn.execute(sql, chunk_ids)
        rows = cur.fetchall()

        results = []
        for row in rows:
            results.append(
                {
                    "chunk_id": row[0],
                    "document_id": row[1],
                    "source_path": row[2],
                    "modality": row[3],
                    "chunk_index": row[4],
                    "start_offset": row[5],
                    "end_offset": row[6],
                    "chunk_version": row[7],
                    "normalization_version": row[8],
                }
            )

        return results

    def count_chunks(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM chunks;")
        return int(cur.fetchone()[0])

    def has_chunk(self, chunk_id: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM chunks WHERE chunk_id = ? LIMIT 1;", (chunk_id,)
        )
        return cur.fetchone() is not None
