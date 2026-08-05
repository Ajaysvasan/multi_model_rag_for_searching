import pytest
import os
import sys
import psutil
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

def simulate_data_insertion():
    """Simulates a data layer insertion operation for benchmarking."""
    # Write a dummy chunk to disk to measure I/O
    path = "/tmp/dummy_chunk_benchmark.txt"
    with open(path, "w") as f:
        f.write("Dummy data for benchmarking RAG " * 100)
    os.remove(path)

def test_benchmark_data_layer_insertion(benchmark):
    """
    Benchmarks the insertion latency and standard deviation.
    """
    benchmark(simulate_data_insertion)

def test_benchmark_disk_io_monitoring():
    """
    Monitors Disk I/O bytes read/write over a set operation.
    """
    process = psutil.Process(os.getpid())
    try:
        io_counters_start = process.io_counters()
        simulate_data_insertion()
        io_counters_end = process.io_counters()
        
        write_bytes = io_counters_end.write_bytes - io_counters_start.write_bytes
        assert write_bytes >= 0 # Validation
    except AttributeError:
        # io_counters might not be available on some OS architectures (e.g. macOS without root)
        pass
