import hashlib
import os
import sys
from pathlib import Path
from typing import Dict, List
from uuid import UUID

import numpy as np
from sqlalchemy.orm import Session

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
project_dir = os.path.dirname(parent_dir)
sys.path.append(project_dir)

from config import Config
from data_layer.ingest.chunker import TextChunker
from data_layer.ingest.normalizer import NormalizationProfiles
from data_layer.ingest.storage.embedding import EmbeddingRecord
from data_layer.ingest.storage.hnsw import HNSWIndex
from data_layer.ingest.Text_files_processing.file_loader import FileLoader
from data_layer.ingest.Text_files_processing.text_extractor import TextExtractor
from system_services.server.pg_chunk_store import PgChunkStore
from system_services.server.user_faiss_manager import UserFaissManager


def ingestion_pipeline(user_id: UUID, file_path_str: str, shared_components: dict):
    """
    Server-side ingestion pipeline using PostgreSQL + User-scoped FAISS.
    """
    print(f"Starting ingestion for user {user_id} on path: {file_path_str}")

    embed_model = shared_components["embed_model"]
    faiss_manager: UserFaissManager = shared_components["faiss_manager"]
    pg_store = PgChunkStore()

    path_obj = Path(file_path_str)
    if not path_obj.exists():
        print(f"Path does not exist: {file_path_str}")
        return {"error": "Path not found"}

    # Determine file category
    loaded_files = {"docs": [], "txt": [], "pdf": [], "image": [], "audio": []}
    
    if path_obj.is_file():
        ext = path_obj.suffix.lower()
        if ext in {".doc", ".docx"}:
            loaded_files["docs"].append(path_obj)
        elif ext == ".txt":
            loaded_files["txt"].append(path_obj)
        elif ext == ".pdf":
            loaded_files["pdf"].append(path_obj)
        elif ext in {".jpg", ".jpeg", ".png"}:
            loaded_files["image"].append(path_obj)
        elif ext in {".mp3", ".wav", ".m4a", ".flac", ".ogg"}:
            loaded_files["audio"].append(path_obj)
        else:
            print(f"Unsupported file extension: {ext}")
            return {"status": "skipped", "reason": "unsupported_extension"}
    else:
        # Load directory
        loader = FileLoader(path_obj)
        loaded_files = loader.load_files()

    # Extract text
    text_files = {k: v for k, v in loaded_files.items() if k in ("docs", "txt", "pdf")}
    extractor = TextExtractor()
    extracted_texts = extractor.extract_all(text_files)

    # Normalize
    normalizer = NormalizationProfiles.rag_ingestion()
    normalized_texts = normalizer.normalize_all(extracted_texts)

    # Chunk
    chunker = TextChunker(
        target_tokens=Config.CHUNK_SIZE,
        max_tokens=int(Config.CHUNK_SIZE * 1.25),
        overlap_tokens=Config.CHUNK_OVERLAP,
    )

    embedding_records = []
    chunk_rows = []
    embedding_rows = []

    # Get user index
    user_index = faiss_manager.get_index(user_id)
    start_faiss_id = user_index.index.ntotal

    print(f"Processing {len(normalized_texts)} textual files...")

    for file_path, text in normalized_texts.items():
        filename = os.path.basename(file_path)
        doc_id = pg_store.add_document_if_not_exists(user_id, str(file_path), filename, "text")

        chunks = chunker.chunk(
            text=text,
            document_id=str(doc_id),
            normalization_version=Config.NORMALIZATION_VERSION,
        )

        for i, ch in enumerate(chunks):
            # Check for existing chunk to maintain idempotency
            if ch.chunk_id in user_index:
                continue

            # Check if exists in Postgres (double check)
            existing_pg = pg_store.get_by_ids([ch.chunk_id], user_id)
            if existing_pg:
                continue

            # Compute embedding

            vec = embed_model.encode(ch.text, normalize_embeddings=True)
            vec_list = np.asarray(vec, dtype="float32").tolist()

            current_faiss_id = start_faiss_id + len(embedding_records)

            embedding_records.append(
                EmbeddingRecord(
                    embedding_id=ch.chunk_id,  # This maps to ID in HNSW
                    chunk_id=ch.chunk_id,
                    document_id=str(doc_id),
                    vector=vec_list,
                    embedding_model_id=Config.EMBEDDING_MODEL_ID,
                    embedding_dim=len(vec_list),
                )
            )

            chunk_rows.append({
                "chunk_id": ch.chunk_id,
                "user_id": user_id,
                "document_id": doc_id,
                "chunk_index": ch.chunk_index,
                "start_offset": ch.start_char,
                "end_offset": ch.end_char,
                "chunk_text": ch.text,
            })

            embedding_rows.append({
                "chunk_id": ch.chunk_id,
                "user_id": user_id,
                "faiss_id": current_faiss_id,
            })

    # Add to FAISS

    if embedding_records:
        user_index.add(embedding_records)
        user_index.save()
        print(f"Added {len(embedding_records)} vectors to FAISS for user {user_id}")

    # Add to Postgres
    if chunk_rows:
        pg_store.insert_chunks(chunk_rows)
        pg_store.insert_embeddings(embedding_rows)
        print(f"Inserted {len(chunk_rows)} chunks into PostgreSQL")

    return {
        "status": "success",
        "processed_files": len(normalized_texts),
        "chunks_added": len(chunk_rows),
    }

if __name__ == "__main__":
    pass
