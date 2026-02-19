import os
import sys
from typing import Any, Dict, List
from uuid import UUID

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
project_dir = os.path.dirname(parent_dir)
sys.path.append(project_dir)

from data_models.chunks import Chunk, Document, Embedding
from data_models.session import SessionLocal


class PgChunkStore:
    def get_by_ids(self, chunk_ids: List[str], user_id: UUID) -> List[Dict[str, Any]]:
        if not chunk_ids:
            return []

        db = SessionLocal()
        try:
            rows = (
                db.query(Chunk)
                .filter(Chunk.id.in_(chunk_ids), Chunk.user_id == user_id)
                .all()
            )

            lookup = {}
            for row in rows:
                lookup[row.id] = {
                    "chunk_id": row.id,
                    "document_id": str(row.document_id),
                    "source_path": "",
                    "modality": "",
                    "chunk_index": row.chunk_index,
                    "start_offset": row.start_char,
                    "end_offset": row.end_char,
                    "chunk_version": "",
                    "normalization_version": "",
                    "chunk_text": row.text or "",
                }

            return [lookup[cid] for cid in chunk_ids if cid in lookup]
        finally:
            db.close()

    def get_source_paths(self, chunk_ids: List[str], user_id: UUID) -> Dict[str, str]:
        if not chunk_ids:
            return {}

        db = SessionLocal()
        try:
            from data_models.chunks import Document

            rows = (
                db.query(Chunk.id, Document.original_path, Document.filename)
                .join(Document, Chunk.document_id == Document.id)
                .filter(Chunk.id.in_(chunk_ids), Chunk.user_id == user_id)
                .all()
            )

            result = {}
            for chunk_id, original_path, filename in rows:
                result[chunk_id] = original_path or filename
            return result
        finally:
            db.close()

    def add_document_if_not_exists(
        self, user_id: UUID, file_path: str, filename: str, modality: str
    ) -> UUID:
        db = SessionLocal()
        try:
            doc = (
                db.query(Document)
                .filter(
                    Document.user_id == user_id,
                    Document.original_path == file_path,
                )
                .first()
            )
            if doc:
                return doc.id

            new_doc = Document(
                user_id=user_id,
                filename=filename,
                original_path=file_path,
                modality=modality,
            )
            db.add(new_doc)
            db.commit()
            db.refresh(new_doc)
            return new_doc.id
        finally:
            db.close()

    def insert_chunks(self, chunks_data: List[dict]):
        if not chunks_data:
            return

        db = SessionLocal()
        try:
            chunks_to_add = []
            for c in chunks_data:
                chunks_to_add.append(
                    Chunk(
                        id=c["chunk_id"],
                        user_id=c["user_id"],
                        document_id=c["document_id"],
                        chunk_index=c["chunk_index"],
                        start_char=c["start_offset"],
                        end_char=c["end_offset"],
                        text=c["chunk_text"],
                    )
                )
            # Use bulk_save_objects for performance if needed, but add_all works
            db.add_all(chunks_to_add)
            db.commit()
        finally:
            db.close()

    def insert_embeddings(self, embeddings_data: List[dict]):
        if not embeddings_data:
            return

        db = SessionLocal()
        try:
            embeddings_to_add = []
            for e in embeddings_data:
                embeddings_to_add.append(
                    Embedding(
                        chunk_id=e["chunk_id"],
                        user_id=e["user_id"],
                        faiss_id=e["faiss_id"],
                    )
                )
            db.add_all(embeddings_to_add)
            db.commit()
        finally:
            db.close()
