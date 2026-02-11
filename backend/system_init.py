import os
import uuid

from sentence_transformers import SentenceTransformer

from cache_layer.cache import TopicCacheManager
from config import Config
from data_layer.chunkstore.Chunkstore import ChunkMetadataStore
from data_layer.ingest.storage.conversation_memory import ConversationMemory
from data_layer.ingest.storage.hnsw import HNSWIndex
from history_layer.history import ConversationHistory
from ingestion_pipeline import check_ingestion_exists, run_ingestion
from retrieval_layer.retrieval_engine import RetrievalEngine

INDEX_PATH = Config.INDEX_PATH
METADATA_DB_PATH = Config.METADATA_DB_PATH
EMBED_MODEL_NAME = Config.EMBED_MODEL_NAME


def initialize_system(ingestion_config=None):

    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(METADATA_DB_PATH), exist_ok=True)

    print("=" * 60)
    print("INITIALIZING RAG SYSTEM")
    print("=" * 60)
    print()

    print("[1/7] Loading embedding model...")
    embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    dim = embed_model.get_sentence_embedding_dimension()
    print(f"       ✓ {EMBED_MODEL_NAME} (dim={dim})")

    if ingestion_config is not None:
        print("\n[2/7] Running ingestion (config provided)...")
        run_ingestion(embed_model, dim, ingestion_config)
    elif not check_ingestion_exists():
        from ingestion_menu import collect_ingestion_config

        print("\n[2/7] No existing index found — first-time ingestion required.")
        ingestion_config = collect_ingestion_config()
        run_ingestion(embed_model, dim, ingestion_config)
    else:
        print("[2/7] ✓ Existing index found — skipping ingestion.")

    print("[3/7] Loading FAISS index...")
    index = HNSWIndex(dim=dim, index_path=INDEX_PATH)
    index.load()
    print(f"       ✓ Loaded {index.index.ntotal} vectors")

    print("[4/7] Loading metadata store...")
    metadata_store = ChunkMetadataStore(db_path=METADATA_DB_PATH)
    print(f"       ✓ Loaded {metadata_store.count_chunks()} chunks")

    print("[5/7] Initializing cache, history, and conversation memory...")
    cache = TopicCacheManager()
    history = ConversationHistory(
        session_id="default",
        db_path=str(Config.CACHE_HISTORY_DB_PATH),
        sim_threshold=0.90,
    )
    session_id = str(uuid.uuid4())[:8]
    conv_memory = ConversationMemory(
        db_path=str(Config.CACHE_HISTORY_DB_PATH),
        max_turns=10,
    )
    print(
        f"       ✓ Cache, history, and conversation memory ready (session={session_id})"
    )

    print("[6/7] Loading LLM model (this may take a while on first run)...")
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

    print("[7/7] Building retrieval engine...")
    engine = RetrievalEngine(
        cache=cache,
        index=index,
        embedding_model=embed_model,
        history=history,
        ann_top_k=Config.ANN_TOP_K,
        history_enabled=True,
        metadata_store=metadata_store,
        generator=generator,
        conversation_memory=conv_memory,
    )
    print("       ✓ Engine ready")

    print()
    print("=" * 60)
    print("SYSTEM READY")
    print("=" * 60)

    return engine, metadata_store, conv_memory, session_id
