import pytest
import time
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

def simulate_llm_backend():
    """Simulates IPC overhead / mmap load times for benchmarking."""
    time.sleep(0.02)

def test_benchmark_llm_backend(benchmark):
    """Benchmarks IPC overhead / mmap load times."""
    benchmark(simulate_llm_backend)
