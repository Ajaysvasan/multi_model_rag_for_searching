import pytest
import time
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

def simulate_adpatermodule():
    """Simulates serialization/deserialization latency for benchmarking."""
    time.sleep(0.001)

def test_benchmark_AdpaterModule(benchmark):
    """Benchmarks serialization/deserialization latency."""
    benchmark(simulate_adpatermodule)
