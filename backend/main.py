"""
RAG System Main Entry Point.

All initialization (models, cache, history, LLM) happens BEFORE the query loop.
The query experience is clean with no loading messages.
"""

import os
import sys

from config import Config

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import numpy as np
from sentence_transformers import SentenceTransformer

from cache_layer.cache import TopicCacheManager
from data_layer.chunkstore.Chunkstore import ChunkMetadataStore
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
        max_tokens=int(CHUNK_SIZE * 1.25),
        overlap_tokens=CHUNK_OVERLAP,
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

            # Prepare metadata row for SQLite - INCLUDING chunk text
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
                    "chunk_text": ch.text,  # Store the actual text!
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


def initialize_system():
    """
    Initialize ALL components upfront before any user interaction.
    Returns fully initialized engine ready for queries.
    """
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(METADATA_DB_PATH), exist_ok=True)
    
    print("=" * 60)
    print("INITIALIZING RAG SYSTEM")
    print("=" * 60)
    print()
    
    # 1. Load embedding model
    print("[1/6] Loading embedding model...")
    embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    dim = embed_model.get_sentence_embedding_dimension()
    print(f"       ✓ {EMBED_MODEL_NAME} (dim={dim})")
    
    # 2. Check/run ingestion
    if not check_ingestion_exists():
        print("\n[2/6] Running first-time ingestion...")
        run_ingestion(embed_model, dim)
    else:
        print("[2/6] ✓ Index and database found")
    
    # 3. Load FAISS index
    print("[3/6] Loading FAISS index...")
    index = HNSWIndex(dim=dim, index_path=INDEX_PATH)
    index.load()
    print(f"       ✓ Loaded {index.index.ntotal} vectors")
    
    # 4. Load metadata store
    print("[4/6] Loading metadata store...")
    metadata_store = ChunkMetadataStore(db_path=METADATA_DB_PATH)
    print(f"       ✓ Loaded {metadata_store.count_chunks()} chunks")
    
    # 5. Initialize cache and history
    print("[5/6] Initializing cache and history...")
    cache = TopicCacheManager()
    history = ConversationHistory(
        session_id="default",
        db_path=str(Config.CACHE_HISTORY_DB_PATH),
        sim_threshold=0.90,
    )
    print("       ✓ Cache and history ready")
    
    # 6. Initialize LLM generator
    print("[6/6] Loading LLM model (this may take a while on first run)...")
    
    # Check if model exists
    from generation_layer.generator import LlamaGenerator
    generator = LlamaGenerator(
        model_name=Config.GENERATION_MODEL,
        models_dir=str(Config.MODELS_DIR),
    )
    
    if generator.is_model_cached():
        print(f"       Found cached model: {Config.GENERATION_MODEL}")
    else:
        print(f"       Downloading model: {Config.GENERATION_MODEL}")
        print("       This is a one-time download (~16GB)...")
    
    generator.load_model(show_progress=True)
    print("       ✓ LLM ready")
    
    # Create retrieval engine with pre-loaded generator
    engine = RetrievalEngine(
        cache=cache,
        index=index,
        embedding_model=embed_model,
        history=history,
        ann_top_k=Config.ANN_TOP_K,
        history_enabled=True,
        metadata_store=metadata_store,
        generator=generator,  # Pass pre-loaded generator
    )
    
    print()
    print("=" * 60)
    print("SYSTEM READY")
    print("=" * 60)
    
    return engine, metadata_store


def run_query_loop(engine):
    """
    Interactive query loop. All initialization is done - queries are instant.
    """
    print()
    print("Type your question to get an answer with sources.")
    print("Commands: /retrieve <query> for chunks only, quit to exit")
    print()
    
    while True:
        try:
            # Clean prompt
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ["quit", "exit", "q"]:
                print("\nGoodbye!")
                break
            
            # Parse command
            if user_input.startswith("/retrieve "):
                query = user_input[10:].strip()
                mode = "retrieve"
            else:
                query = user_input
                mode = "answer"
            
            if mode == "retrieve":
                # Simple retrieval mode
                results = engine.retrieve_with_metadata(query)
                
                if not results:
                    print("\nNo results found.\n")
                    continue
                
                print(f"\nFound {len(results)} relevant chunks:\n")
                for i, meta in enumerate(results, 1):
                    print(f"[{i}] {meta['source_path']}")
                    text_preview = meta.get('chunk_text', '')[:150].replace('\n', ' ')
                    if text_preview:
                        print(f"    {text_preview}...")
                print()
            
            else:
                # Full RAG mode - generate answer
                response = engine.retrieve_and_generate(query)
                
                # Clean GPT-style output
                print(f"\nAssistant: {response.answer}")
                
                if response.citations:
                    print("\n" + "-" * 40)
                    print("Sources:")
                    for citation in response.citations:
                        source_name = os.path.basename(citation['source_path'])
                        print(f"  [{citation['id']}] {source_name}")
                
                print()
        
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}\n")


def main():
    """Main entry point."""
    try:
        # Initialize everything upfront
        engine, metadata_store = initialize_system()
        
        # Run query loop (no loading during queries)
        run_query_loop(engine)
        
        # Cleanup
        metadata_store.close()
        
    except KeyboardInterrupt:
        print("\n\nInterrupted during initialization.")
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
