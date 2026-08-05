import pytest
import time
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

def simulate_history_layer():
    """Simulates retrieving chat history for benchmarking."""
    time.sleep(0.003)

def test_benchmark_history_layer(benchmark):
    """Benchmarks retrieving chat history."""
    benchmark(simulate_history_layer)
