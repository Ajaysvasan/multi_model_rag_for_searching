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

from cache_layer.cache import TopicCacheManager
from data_layer.chunkstore.Chunkstore import (
    ChunkMetadataStore,
)  # your SQLite-backed store
from data_layer.ingest.chunker import TextChunker
from data_layer.ingest.normalizer import NormalizationProfiles
from data_layer.ingest.storage.embedding import EmbeddingRecord
from data_layer.ingest.storage.hnsw import HNSWIndex
from data_layer.ingest.Text_files_processing.file_loader import FileLoader
from data_layer.ingest.Text_files_processing.text_extractor import TextExtractor
from history_layer.history import ConversationHistory
from retrieval_layer.retrieval_engine import RetrievalEngine

DATASET_PATH = Config.DATASET_PATH
INDEX_PATH = Config.INDEX_PATH
METADATA_PATH = Config.METADATA_PATH
METADATA_DB_PATH = Config.METADATA_DB_PATH

EMBED_MODEL_NAME = Config.EMBED_MODEL_NAME
CHUNK_SIZE = Config.CHUNK_SIZE
CHUNK_OVERLAP = Config.CHUNK_OVERLAP


def check_ingestion_exists():
    """Check if ingestion has already been done."""
    index_exists = os.path.exists(INDEX_PATH) and os.path.exists(
        str(INDEX_PATH) + ".ids"
    )
    db_exists = os.path.exists(METADATA_DB_PATH)
    return index_exists and db_exists


def run_ingestion(model, dim):
    """Run the ingestion process."""
    print("\n" + "=" * 60)
    print("Starting Ingestion Process")
    print("=" * 60 + "\n")

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
    chunker = TextChunker(
        target_tokens=CHUNK_SIZE,
        max_tokens=int(CHUNK_SIZE * 1.25),  # Allow 25% growth max
        overlap_tokens=CHUNK_OVERLAP
    )

    print("Chunking + embedding...")

    # Initialize metadata store (SQLite)
    metadata_store = ChunkMetadataStore(db_path=METADATA_DB_PATH)

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

    print("\n" + "=" * 60)
    print("Ingestion Complete!")
    print("=" * 60)

    return index


def run_retrieval(model, dim):
    """Run the retrieval/query system."""
    print("\n" + "=" * 60)
    print("Initializing Retrieval Engine")
    print("=" * 60 + "\n")

    # Initialize FAISS HNSW index
    index = HNSWIndex(
        dim=dim,
        index_path=INDEX_PATH,
    )

    # Load the existing index
    index.load()
    print(f"Loaded FAISS index with {index.index.ntotal} vectors")

    # Initialize metadata store
    metadata_store = ChunkMetadataStore(db_path=METADATA_DB_PATH)
    print(f"Loaded metadata store with {metadata_store.count_chunks()} chunks")

    # Initialize cache and history
    cache = TopicCacheManager()

    history = ConversationHistory(
        session_id="default",
        db_path=str(Config.CACHE_HISTORY_DB_PATH),
        sim_threshold=0.90  # Increased from 0.80 for more precise matching
    )

    # Create retrieval engine
    engine = RetrievalEngine(
        cache=cache,
        index=index,
        embedding_model=model,
        history=history,
        ann_top_k=Config.ANN_TOP_K,
        history_enabled=True,
        metadata_store=metadata_store,
    )

    print("\n" + "=" * 60)
    print("RAG System Ready! You can now query your documents.")
    print("=" * 60)
    print("Type 'quit' or 'exit' to stop.\n")

    # Interactive query loop
    while True:
        try:
            query = input("\nEnter your query: ").strip()

            if not query:
                continue

            if query.lower() in ["quit", "exit", "q"]:
                print("\nExiting...")
                break

            print(f"\nSearching for: '{query}'")
            print("-" * 60)

            # Retrieve chunk IDs and metadata
            results = engine.retrieve_with_metadata(query)

            if not results:
                print("No results found.")
                continue

            print(f"\nFound {len(results)} relevant chunks:\n")

            for i, meta in enumerate(results, 1):
                print(f"Result {i}:")
                print(f"  Source: {meta['source_path']}")
                print(f"  Chunk Index: {meta['chunk_index']}")
                print(f"  Offsets: {meta['start_offset']} - {meta['end_offset']}")
                print(f"  Modality: {meta['modality']}")
                print()

        except KeyboardInterrupt:
            print("\n\nInterrupted. Exiting...")
            break
        except Exception as e:
            print(f"\nError: {e}")
            import traceback

            traceback.print_exc()

    # Cleanup
    metadata_store.close()
    print("\nClosed metadata store. Goodbye!")


def main():
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(METADATA_DB_PATH), exist_ok=True)

    # Load embedding model
    print("Loading embedding model...")
    model = SentenceTransformer(EMBED_MODEL_NAME)
    dim = model.get_sentence_embedding_dimension()
    print(f"Model loaded: {EMBED_MODEL_NAME} (dim={dim})")

    # Check if ingestion has already been done
    if check_ingestion_exists():
        print("\n✓ Found existing index and database. Skipping ingestion.")
        print("  To re-run ingestion, delete:")
        print(f"    - {INDEX_PATH}")
        print(f"    - {INDEX_PATH}.ids")
        print(f"    - {METADATA_DB_PATH}")
        run_retrieval(model, dim)
    else:
        print("\n✗ No existing index found. Running ingestion first...")
        run_ingestion(model, dim)
        print("\nNow starting retrieval system...")
        run_retrieval(model, dim)


if __name__ == "__main__":
    main()
