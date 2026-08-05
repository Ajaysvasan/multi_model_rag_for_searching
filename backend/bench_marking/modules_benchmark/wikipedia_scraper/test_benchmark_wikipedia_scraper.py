import pytest
import time
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

def simulate_wikipedia_scraper():
    """Simulates web scraping/parsing throughput for benchmarking."""
    time.sleep(0.1)

def test_benchmark_wikipedia_scraper(benchmark):
    """Benchmarks web scraping/parsing throughput."""
    benchmark(simulate_wikipedia_scraper)
