import os
import sys
from platform import system

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
project_dir = os.path.dirname(parent_dir)
sys.path.append(project_dir)

from sentence_transformers import SentenceTransformer

from config import Config
from generation_layer.generator import LlamaGenerator, MmapGenerator

from .pg_cache import PgTopicCache
from .pg_conversation_memory import PgConversationMemory
from .pg_history import PgConversationHistory
from .user_faiss_manager import UserFaissManager

EMBED_MODEL_NAME = Config.EMBED_MODEL_NAME


def load_shared_components():
    print("[1/3] Loading embedding model...")
    embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    dim = embed_model.get_sentence_embedding_dimension()
    print(f"       {EMBED_MODEL_NAME} (dim={dim})")

    print("[2/3] Loading LLM model (this may take a while on first run)...")

    generator = LlamaGenerator(
        model_name=Config.GENERATION_MODEL,
        models_dir=str(Config.MODELS_DIR),
    )
    if generator.is_model_cached():
        print(f"       Found cached model: {Config.GENERATION_MODEL}")
    else:
        print(f"       Downloading model: {Config.GENERATION_MODEL}")
    generator.load_model(show_progress=True)
    print("       LLM ready")

    print("[3/3] Initializing shared services...")
    faiss_manager = UserFaissManager(dim=dim)
    pg_cache = PgTopicCache()
    pg_history = PgConversationHistory()
    pg_conv_memory = PgConversationMemory()
    print("       Shared services ready")

    return {
        "embed_model": embed_model,
        "dim": dim,
        "generator": generator,
        "faiss_manager": faiss_manager,
        "pg_cache": pg_cache,
        "pg_history": pg_history,
        "pg_conv_memory": pg_conv_memory,
    }
