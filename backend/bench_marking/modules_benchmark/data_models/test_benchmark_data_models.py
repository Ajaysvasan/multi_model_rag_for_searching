import pytest
import time
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

def simulate_data_models():
    """Simulates Pydantic object creation latency for benchmarking."""
    time.sleep(0.0005)

def test_benchmark_data_models(benchmark):
    """Benchmarks Pydantic object creation latency."""
    benchmark(simulate_data_models)
