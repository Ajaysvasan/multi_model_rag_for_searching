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


if __name__ == "__main__":
    test_config = Config()
