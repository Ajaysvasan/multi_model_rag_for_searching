import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
project_dir = os.path.dirname(parent_dir)
sys.path.append(project_dir)
import uuid
from platform import system

from sentence_transformers import SentenceTransformer

from cache_layer.cache import TopicCacheManager
from config import Config
from data_layer.chunkstore.Chunkstore import ChunkMetadataStore
from data_layer.ingest.storage.conversation_memory import ConversationMemory
from data_layer.ingest.storage.hnsw import HNSWIndex
from generation_layer.generator import LlamaGenerator, MmapGenerator
from history_layer.history import ConversationHistory
from retrieval_layer.retrieval_engine import QueryProcessing, RetrievalEngine

from .ingestion_pipeline import check_ingestion_exists

INDEX_PATH = Config.INDEX_PATH
METADATA_DB_PATH = Config.METADATA_DB_PATH
EMBED_MODEL_NAME = Config.EMBED_MODEL_NAME


# only do the Initializing, dont't run the ingestion pipeline here if the files are not there throw exception
def initialize_system(ingestion_config=None):

    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(METADATA_DB_PATH), exist_ok=True)

    print("[1/7] Loading embedding model...")
    embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    dim = embed_model.get_sentence_embedding_dimension()
    print(f"{EMBED_MODEL_NAME} (dim={dim})")

    # if ingestion_config is not None:
    #     print("\n[2/7] Running ingestion (config provided)...")
    #     run_ingestion(embed_model, dim, ingestion_config)
    if not check_ingestion_exists():
        raise FileNotFoundError(
            "The index and meta data store were not found. Ingest the data"
        )
        # from ingestion_menu import collect_ingestion_config

        # print("\n[2/7] No existing index found — first-time ingestion required.")
        # ingestion_config = collect_ingestion_config()
        # run_ingestion(embed_model, dim, ingestion_config)
    else:
        print("[2/7] ✓ Existing index found — skipping ingestion.")

    print("[3/7] Loading FAISS index...")
    index = HNSWIndex(dim=dim, index_path=INDEX_PATH)
    index.load()
    print(f"Loaded {index.index.ntotal} vectors")

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
    print(f"Initializing query pre processiong")
    query_preprocessor = QueryProcessing(conv_memory, embedding_model=embed_model)
    print(f"Cache, history, and conversation memory ready (session={session_id})")

    print("[6/7] Loading LLM model (this may take a while on first run)...")

    if system().lower() == "windows":

        generator = LlamaGenerator(
            model_name=Config.GENERATION_MODEL,
            models_dir=str(Config.MODELS_DIR),
        )
        # TODO : FIX SOME BUGS WITH THIS
        # BUG TYPE : CRITICAL
    elif system().lower() in ["linux", "darwin"]:
        geneator = MmapGenerator(
            model_name=Config.GENERATION_MODEL,
            model_path=Config.MODELS_DIR,
            backend_path=Config.BIN_PATH,
        )
    else:
        raise OSError(f"Unsupported operating system : {system()}")

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
    print("LLM ready")

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
    print("SYSTEM READY")

    return engine, metadata_store, conv_memory, session_id, query_preprocessor


if __name__ == "__main__":
    initialize_system()
