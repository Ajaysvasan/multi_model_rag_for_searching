import pytest
import time
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

def simulate_security_layer():
    """Simulates password hashing and JWT token creation for benchmarking."""
    time.sleep(0.04)

def test_benchmark_security_layer(benchmark):
    """Benchmarks password hashing and JWT token creation."""
    benchmark(simulate_security_layer)
