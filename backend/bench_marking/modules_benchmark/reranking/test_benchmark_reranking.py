import pytest
import time
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

def simulate_reranking():
    """Simulates cross-encoder re-ranking latency for benchmarking."""
    time.sleep(0.015)

def test_benchmark_reranking(benchmark):
    """Benchmarks cross-encoder re-ranking latency."""
    benchmark(simulate_reranking)
