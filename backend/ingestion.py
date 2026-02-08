import os
import sys

from config import Config

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import json
from pathlib import Path
from typing import Dict, List

import numpy as np
from sentence_transformers import SentenceTransformer

from data_layer.chunkstore.Chunkstore import (
    ChunkMetadataStore,
)  # your SQLite-backed store
from data_layer.ingest.chunker import TextChunker
from data_layer.ingest.normalizer import NormalizationProfiles
from data_layer.ingest.storage.embedding import EmbeddingRecord
from data_layer.ingest.storage.hnsw import HNSWIndex
from data_layer.ingest.Text_files_processing.file_loader import FileLoader
from data_layer.ingest.Text_files_processing.text_extractor import TextExtractor
from metadata_loader import load_metadata_store

DATASET_PATH = Config.DATASET_PATH
INDEX_PATH = Config.INDEX_PATH
METADATA_PATH = Config.METADATA_PATH

EMBED_MODEL_NAME = Config.EMBED_MODEL_NAME
CHUNK_SIZE = Config.CHUNK_SIZE
CHUNK_OVERLAP = Config.CHUNK_OVERLAP


def main():
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)

    # Load embedding model
    model = SentenceTransformer(EMBED_MODEL_NAME)
    dim = model.get_sentence_embedding_dimension()

    # Init FAISS HNSW
    index = HNSWIndex(
        dim=dim,
        index_path=INDEX_PATH,
    )

    # Load files
    file_loader = FileLoader(DATASET_PATH)
    loaded_files = file_loader.load_files()

    extractor = TextExtractor()
    extracted_texts = extractor.extract_all(loaded_files)

    # Normalize
    normalizer = NormalizationProfiles.rag_ingestion()
    normalized_texts = normalizer.normalize_all(extracted_texts)

    # Chunk
    chunker = TextChunker(target_tokens=CHUNK_SIZE, overlap_tokens=CHUNK_OVERLAP)

    print("Chunking + embedding...")

    # Initialize metadata store (SQLite)
    metadata_store = ChunkMetadataStore(db_path="data/index/chunks.db")

    embedding_records = []
    metadata_rows = []

    for file_path, text in normalized_texts.items():
        chunks = chunker.chunk(
            text=text,
            document_id=str(file_path),
            normalization_version=Config.NORMALIZATION_VERSION,
        )

        for ch in chunks:
            # Embed
            vec = model.encode(ch.text, normalize_embeddings=True)

            # Prepare embedding record for FAISS
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

            # Prepare metadata row for SQLite
            metadata_rows.append(
                {
                    "chunk_id": ch.chunk_id,
                    "document_id": ch.document_id,
                    "source_path": str(file_path),
                    "modality": "text",
                    "chunk_index": ch.chunk_index,
                    "start_offset": ch.start_char,
                    "end_offset": ch.end_char,
                    "chunk_version": str(ch.chunk_version),
                    "normalization_version": str(Config.NORMALIZATION_VERSION),
                }
            )

    # Add embeddings to FAISS
    print(f"Adding {len(embedding_records)} vectors to FAISS...")
    index.add(embedding_records)

    # Save FAISS index
    index.save()
    print(f"FAISS index saved to: {INDEX_PATH}")

    # Insert metadata into SQLite (idempotent)
    print(f"Inserting {len(metadata_rows)} metadata rows into SQLite...")
    metadata_store.insert_many(metadata_rows)

    print("Metadata DB path:", metadata_store.db_path)
    print("Total chunks in DB:", metadata_store.count_chunks())

    metadata_store.close()

    print("Ingestion complete.")


if __name__ == "__main__":
    main()
