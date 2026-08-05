import pytest
import time
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

def simulate_generation_layer():
    """Simulates token generation speed (tokens/sec) for benchmarking."""
    time.sleep(0.05)

def test_benchmark_generation_layer(benchmark):
    """Benchmarks token generation speed (tokens/sec)."""
    benchmark(simulate_generation_layer)
