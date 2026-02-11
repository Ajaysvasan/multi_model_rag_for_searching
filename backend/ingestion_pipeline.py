import hashlib
import os
import sys
from pathlib import Path

import numpy as np

from config import Config
from data_layer.chunkstore.Chunkstore import ChunkMetadataStore
from data_layer.ingest.chunker import TextChunker
from data_layer.ingest.normalizer import NormalizationProfiles
from data_layer.ingest.storage.embedding import EmbeddingRecord
from data_layer.ingest.storage.hnsw import HNSWIndex
from data_layer.ingest.Text_files_processing.file_loader import FileLoader
from data_layer.ingest.Text_files_processing.text_extractor import TextExtractor

_current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(
    0, os.path.join(_current_dir, "data_layer", "ingest", "ImageProcessing")
)
sys.path.insert(
    0, os.path.join(_current_dir, "data_layer", "ingest", "audio_processing")
)

INDEX_PATH = Config.INDEX_PATH
METADATA_DB_PATH = Config.METADATA_DB_PATH
CHUNK_SIZE = Config.CHUNK_SIZE
CHUNK_OVERLAP = Config.CHUNK_OVERLAP


def check_ingestion_exists() -> bool:
    """Return True if a FAISS index and metadata DB already exist on disk."""
    index_exists = os.path.exists(INDEX_PATH) and os.path.exists(
        str(INDEX_PATH) + ".ids"
    )
    db_exists = os.path.exists(METADATA_DB_PATH)
    return index_exists and db_exists


_EXT_TO_CATEGORY = {
    ".doc": "docs",
    ".docx": "docs",
    ".txt": "txt",
    ".pdf": "pdf",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".mp3": "audio",
    ".wav": "audio",
    ".m4a": "audio",
    ".flac": "audio",
    ".ogg": "audio",
}


def _resolve_files(path: Path) -> dict:
    if path.is_dir():
        loader = FileLoader(path)
        return loader.load_files()

    ext = path.suffix.lower()
    cat = _EXT_TO_CATEGORY.get(ext)
    if cat is None:
        print(f"  [WARN] Unsupported file type: {path}")
        return {"docs": [], "txt": [], "pdf": [], "image": [], "audio": []}

    result = {"docs": [], "txt": [], "pdf": [], "image": [], "audio": []}
    result[cat].append(str(path.resolve()))
    return result


def run_ingestion(model, dim: int, ingestion_config: dict) -> HNSWIndex:
    print("\n" + "=" * 60)
    print("Starting Ingestion Process")
    print("=" * 60 + "\n")

    index = HNSWIndex(dim=dim, index_path=INDEX_PATH)

    normalizer = NormalizationProfiles.rag_ingestion()
    chunker = TextChunker(
        target_tokens=CHUNK_SIZE,
        max_tokens=int(CHUNK_SIZE * 1.25),
        overlap_tokens=CHUNK_OVERLAP,
    )
    metadata_store = ChunkMetadataStore(db_path=METADATA_DB_PATH)
    embedding_records = []
    metadata_rows = []

    # ── Text ingestion ──────────────────────────────────────────
    text_path = ingestion_config.get("text")
    if text_path:
        print(f"Loading text files from: {text_path}")
        loaded_files = _resolve_files(Path(text_path))
        text_files = {
            k: v for k, v in loaded_files.items() if k in ("docs", "txt", "pdf")
        }

        extractor = TextExtractor()
        extracted_texts = extractor.extract_all(text_files)
        normalized_texts = normalizer.normalize_all(extracted_texts)

        print("Chunking + embedding text files...")
        for file_path, text in normalized_texts.items():
            chunks = chunker.chunk(
                text=text,
                document_id=str(file_path),
                normalization_version=Config.NORMALIZATION_VERSION,
            )
            for ch in chunks:
                vec = model.encode(ch.text, normalize_embeddings=True)
                embedding_records.append(
                    EmbeddingRecord(
                        embedding_id=ch.chunk_id,
                        chunk_id=ch.chunk_id,
                        document_id=ch.document_id,
                        vector=np.asarray(vec, dtype="float32").tolist(),
                        embedding_model_id=Config.EMBEDDING_MODEL_ID,
                        embedding_dim=dim,
                    )
                )
                metadata_rows.append(
                    {
                        "chunk_id": ch.chunk_id,
                        "document_id": ch.document_id,
                        "source_path": str(Path(file_path).resolve()),
                        "modality": "text",
                        "chunk_index": ch.chunk_index,
                        "start_offset": ch.start_char,
                        "end_offset": ch.end_char,
                        "chunk_version": str(ch.chunk_version),
                        "normalization_version": str(Config.NORMALIZATION_VERSION),
                        "chunk_text": ch.text,
                    }
                )
        print(f"  Text: {len(embedding_records)} chunks")

    image_path = ingestion_config.get("image")
    if image_path:
        print(f"\nLoading images from: {image_path}")
        img_loaded = _resolve_files(Path(image_path))
        image_files = img_loaded.get("image", [])
        if image_files:
            print(f"  Processing {len(image_files)} image(s)...")
            try:
                from image_ingestion import ingest_images

                image_records = ingest_images(image_files)
                for rec in image_records:
                    vec = model.encode(rec["chunk_text"], normalize_embeddings=True)
                    embedding_records.append(
                        EmbeddingRecord(
                            embedding_id=rec["chunk_id"],
                            chunk_id=rec["chunk_id"],
                            document_id=rec["document_id"],
                            vector=np.asarray(vec, dtype="float32").tolist(),
                            embedding_model_id=Config.EMBEDDING_MODEL_ID,
                            embedding_dim=dim,
                        )
                    )
                    metadata_rows.append(
                        {
                            "chunk_id": rec["chunk_id"],
                            "document_id": rec["document_id"],
                            "source_path": rec["source_path"],
                            "modality": "image",
                            "chunk_index": rec["chunk_index"],
                            "start_offset": rec["start_offset"],
                            "end_offset": rec["end_offset"],
                            "chunk_version": Config.CHUNK_VERSION,
                            "normalization_version": Config.NORMALIZATION_VERSION,
                            "chunk_text": rec["chunk_text"],
                        }
                    )
                print(f"  Images: {len(image_records)} chunks")
            except Exception as e:
                print(f"  [WARN] Image ingestion skipped: {e}")
        else:
            print("  No image files found in the directory.")

    audio_path = ingestion_config.get("audio")
    if audio_path:
        print(f"\nLoading audio from: {audio_path}")
        aud_loaded = _resolve_files(Path(audio_path))
        audio_files = aud_loaded.get("audio", [])
        if audio_files:
            print(f"  Processing {len(audio_files)} audio file(s)...")
            try:
                from audio_ingestion import ingest_audio

                transcripts = ingest_audio(audio_files)
                for audio_file_path, transcript in transcripts.items():
                    normalized = normalizer.normalize_text(transcript)
                    doc_id = hashlib.sha256(audio_file_path.encode()).hexdigest()
                    chunks = chunker.chunk(
                        text=normalized,
                        document_id=doc_id,
                        normalization_version=Config.NORMALIZATION_VERSION,
                    )
                    for ch in chunks:
                        vec = model.encode(ch.text, normalize_embeddings=True)
                        embedding_records.append(
                            EmbeddingRecord(
                                embedding_id=ch.chunk_id,
                                chunk_id=ch.chunk_id,
                                document_id=ch.document_id,
                                vector=np.asarray(vec, dtype="float32").tolist(),
                                embedding_model_id=Config.EMBEDDING_MODEL_ID,
                                embedding_dim=dim,
                            )
                        )
                        metadata_rows.append(
                            {
                                "chunk_id": ch.chunk_id,
                                "document_id": ch.document_id,
                                "source_path": audio_file_path,
                                "modality": "audio",
                                "chunk_index": ch.chunk_index,
                                "start_offset": ch.start_char,
                                "end_offset": ch.end_char,
                                "chunk_version": str(ch.chunk_version),
                                "normalization_version": str(
                                    Config.NORMALIZATION_VERSION
                                ),
                                "chunk_text": ch.text,
                            }
                        )
                print(f"  Audio: {len(transcripts)} files transcribed")
            except Exception as e:
                print(f"  [WARN] Audio ingestion skipped: {e}")
        else:
            print("  No audio files found in the directory.")

    print(f"\nAdding {len(embedding_records)} total vectors to FAISS...")
    index.add(embedding_records)
    index.save()
    print(f"FAISS index saved to: {INDEX_PATH}")

    metadata_store.insert_many(metadata_rows)
    print(f"Total chunks in DB: {metadata_store.count_chunks()}")
    metadata_store.close()

    print("\n" + "=" * 60)
    print("Ingestion Complete!")
    print("=" * 60)
    return index
