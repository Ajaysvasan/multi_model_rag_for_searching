import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
from sentence_transformers import SentenceTransformer

from cache_layer.cache import TopicCacheManager
from data_layer.ingest.storage.hnsw import HNSWIndex
from retrieval_layer.retrieval_engine import RetrievalEngine

# Load components
model = SentenceTransformer("all-MiniLM-L6-v2")

index = HNSWIndex(
    dim=model.get_sentence_embedding_dimension(),
    index_path="data/index/faiss_hnsw.index",
)
index.load()

cache = TopicCacheManager()

engine = RetrievalEngine(
    cache=cache,
    index=index,
    embedding_model=model,
    ann_top_k=5,
)

# Try some queries
queries = [
    "operating systems pdf",
    "linux scheduling",
    "operating systems pdf",  # should HIT cache
]

for q in queries:
    chunks = engine.retrieve(q)
    print(f"\nQuery: {q}")
    print("Chunks:", chunks)
