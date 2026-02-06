# Don't assume the directory path as it is given by the user from the end.
# So keep things in that way
from pathlib import Path


class Config:
    DATASET_PATH = Path("data/datasets")
    INDEX_PATH = Path("data/index/faiss_hnsw.index")

    NORMALIZATION_VERSION = "rag_v1"
    CHUNK_VERSION = "chunk_v1"
    EMBEDDING_MODEL_ID = "embedding_v1"

    EMBEDDING_BATCH_SIZE = 64
    ANN_TOP_K = 5
    METADATA_DB_PATH = Path("data/index/chunks.db")


if __name__ == "__main__":
    test_config = Config()
