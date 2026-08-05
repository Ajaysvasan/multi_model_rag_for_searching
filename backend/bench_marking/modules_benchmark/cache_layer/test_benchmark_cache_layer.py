import pytest
import time
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

def simulate_cache_layer():
    """Simulates cache set/get latency for benchmarking."""
    time.sleep(0.002)

def test_benchmark_cache_layer(benchmark):
    """Benchmarks cache set/get latency."""
    benchmark(simulate_cache_layer)
