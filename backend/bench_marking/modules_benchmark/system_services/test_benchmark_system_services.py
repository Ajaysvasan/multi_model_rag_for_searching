import pytest
import time
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

def simulate_system_services():
    """Simulates orchestration/queue overhead for benchmarking."""
    time.sleep(0.005)

def test_benchmark_system_services(benchmark):
    """Benchmarks orchestration/queue overhead."""
    benchmark(simulate_system_services)
