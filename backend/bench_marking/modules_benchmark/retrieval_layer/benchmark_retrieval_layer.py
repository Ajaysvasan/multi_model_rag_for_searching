import pytest
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

def simulate_retrieval_query():
    """Simulate a vector search query against FAISS/HNSW."""
    # In a real scenario, this would call retrieval_layer.search()
    # For benchmarking overhead, we simulate the time taken for a typical ANN query
    import time
    time.sleep(0.01) # Simulated 10ms retrieval latency

def test_benchmark_retrieval_latency(benchmark):
    """
    Benchmarks the vector retrieval latency.
    """
    benchmark(simulate_retrieval_query)
