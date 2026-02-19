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
from data_layer.ingest.Text_files_processing.file_loader import FileLoader
from data_layer.ingest.Text_files_processing.text_extractor import TextExtractor
from system_services.server.pg_chunk_store import PgChunkStore
from system_services.server.user_faiss_manager import UserFaissManager

from data_layer.ingest.audio_processing.audio_ingestion import ingest_audio
from data_layer.ingest.ImageProcessing.image_ingestion import ingest_images


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
        loader = FileLoader(path_obj)
        loaded_by_loader = loader.load_files()
        for k, v in loaded_by_loader.items():
            if k in loaded_files:
                loaded_files[k].extend(v)

    audio_paths = [str(p) for p in loaded_files["audio"]]
    if audio_paths:
        print(f"Processing {len(audio_paths)} audio files...")
        audio_transcripts = ingest_audio(
            audio_paths, 
            model_name="small",
            model_dir="./models/whisper"
        )
    else:
        audio_transcripts = {}

    text_files = {k: v for k, v in loaded_files.items() if k in ("docs", "txt", "pdf")}
    extractor = TextExtractor()
    extracted_texts = extractor.extract_all(text_files)

    for path_str, transcript in audio_transcripts.items():
        extracted_texts[path_str] = transcript

    normalizer = NormalizationProfiles.rag_ingestion()
    normalized_texts = normalizer.normalize_all(extracted_texts)

    chunker = TextChunker(
        target_tokens=Config.CHUNK_SIZE,
        max_tokens=int(Config.CHUNK_SIZE * 1.25),
        overlap_tokens=Config.CHUNK_OVERLAP,
    )

    embedding_records = []
    chunk_rows = []
    embedding_rows = []

    user_index = faiss_manager.get_index(user_id)
    start_faiss_id = user_index.index.ntotal

    print(f"Processing {len(normalized_texts)} textual items (files + audio)...")

    for file_path, text in normalized_texts.items():
        filename = os.path.basename(file_path)
        # For audio, modality is treated as "text" since we ingest the transcript
        doc_id = pg_store.add_document_if_not_exists(user_id, str(file_path), filename, "text")

        chunks = chunker.chunk(
            text=text,
            document_id=str(doc_id),
            normalization_version=Config.NORMALIZATION_VERSION,
        )

        for i, ch in enumerate(chunks):
            if ch.chunk_id in user_index:
                continue
            
            existing_pg = pg_store.get_by_ids([ch.chunk_id], user_id)
            if existing_pg:
                continue

            vec = embed_model.encode(ch.text, normalize_embeddings=True)
            vec_list = np.asarray(vec, dtype="float32").tolist()

            current_faiss_id = start_faiss_id + len(embedding_records)

            embedding_records.append(
                EmbeddingRecord(
                    embedding_id=ch.chunk_id,
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

    image_paths = [str(p) for p in loaded_files["image"]]
    if image_paths:
        print(f"Processing {len(image_paths)} images...")
        image_records = ingest_images(image_paths)
        
        for rec in image_records:
            c_id = rec["chunk_id"]
            
            if c_id in user_index:
                continue
            if pg_store.get_by_ids([c_id], user_id):
                continue
            
            filename = os.path.basename(rec["source_path"])
            
            # Ensure document existence and get consistent ID from Postgres.
            # We then regenerate the chunk ID based on this system-consistent doc_id 
            # to maintain integrity, rather than using the one from image ingestion.
            doc_uuid = pg_store.add_document_if_not_exists(
                user_id, 
                rec["source_path"], 
                filename, 
                "image"
            )
            
            final_doc_id = str(doc_uuid)
            new_chunk_id = hashlib.sha256(f"{final_doc_id}|image|0".encode()).hexdigest()[:16]
            chunk_text = rec["chunk_text"]
            
            vec = embed_model.encode(chunk_text, normalize_embeddings=True)
            vec_list = np.asarray(vec, dtype="float32").tolist()
            
            current_faiss_id = start_faiss_id + len(embedding_records)
            
            embedding_records.append(
                EmbeddingRecord(
                    embedding_id=new_chunk_id,
                    chunk_id=new_chunk_id,
                    document_id=final_doc_id,
                    vector=vec_list,
                    embedding_model_id=Config.EMBEDDING_MODEL_ID,
                    embedding_dim=len(vec_list),
                )
            )
            
            chunk_rows.append({
                "chunk_id": new_chunk_id,
                "user_id": user_id,
                "document_id": final_doc_id,
                "chunk_index": 0,
                "start_offset": 0,
                "end_offset": len(chunk_text),
                "chunk_text": chunk_text,
            })
            
            embedding_rows.append({
                "chunk_id": new_chunk_id,
                "user_id": user_id,
                "faiss_id": current_faiss_id,
            })


    if embedding_records:
        user_index.add(embedding_records)
        user_index.save()
        print(f"Added {len(embedding_records)} vectors to FAISS for user {user_id}")

    if chunk_rows:
        pg_store.insert_chunks(chunk_rows)
        pg_store.insert_embeddings(embedding_rows)
        print(f"Inserted {len(chunk_rows)} chunks into PostgreSQL")

    return {
        "status": "success",
        "processed_files": len(normalized_texts) + len(image_paths),
        "chunks_added": len(chunk_rows),
    }

if __name__ == "__main__":
    pass
