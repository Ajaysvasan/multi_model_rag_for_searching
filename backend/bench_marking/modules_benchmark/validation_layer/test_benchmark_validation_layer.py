import pytest
import time
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

def simulate_validation_layer():
    """Simulates input sanitization speed for benchmarking."""
    time.sleep(0.001)

def test_benchmark_validation_layer(benchmark):
    """Benchmarks input sanitization speed."""
    benchmark(simulate_validation_layer)
