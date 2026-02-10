# Don't assume the directory path as it is given by the user from the end.
# So keep things in that way
from pathlib import Path


class Config:
    DATASET_PATH = Path("data/datasets")
    INDEX_PATH = Path("data/index/faiss_hnsw.index")

    NORMALIZATION_VERSION = "rag_v1"
    CHUNK_VERSION = "chunk_v1"
    EMBEDDING_MODEL_ID = "embedding_v1"
    METADATA_PATH = "data/index/metadata.json"
    EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    CHUNK_SIZE = 256  # Reduced from 800 for more granular chunks
    CHUNK_OVERLAP = 50  # Reduced from 100 proportionally

    EMBEDDING_BATCH_SIZE = 64
    ANN_TOP_K = 5
    METADATA_DB_PATH = Path("data/index/chunks.db")

    L1_CAPACITY = 32
    L2_CAPACITY = 128
    L3_CAPACITY = 1024
    RECENCY_BOOST = 0.2
    L2_THRESHOLD = 8
    L3_THRESHOLD = 3

    CACHE_HISTORY_DB_PATH = Path("data/index/cache_history.db")

    # Reranking Configuration
    RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANK_TOP_K = 5  # Number of results after reranking
    
    # Validation Configuration
    MIN_RELEVANCE_SCORE = 0.3  # Minimum score for chunk to pass validation
    MAX_RETRIES = 2  # Max re-retrieval attempts on validation failure
    
    # Generation Configuration - Local GGUF Model (~4.4GB)
    GENERATION_MODEL = "TheBloke/Mistral-7B-Instruct-v0.2-GGUF"
    GENERATION_MODEL_FILE = "mistral-7b-instruct-v0.2.Q4_K_M.gguf"  # ~4.4GB
    MODELS_DIR = Path("models")
    USE_LOCAL_MODEL = True  # Set False to use HuggingFace API instead


if __name__ == "__main__":
    test_config = Config()
