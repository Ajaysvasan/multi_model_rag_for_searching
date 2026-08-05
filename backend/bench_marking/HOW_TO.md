# Benchmarking Suite Execution Guide

Welcome to the comprehensive benchmarking suite. As an industry-standard practice, we measure not just functional correctness, but also system performance, resource utilization, and retrieval/generation accuracy for this RAG architecture.

## Prerequisites

Ensure all benchmarking dependencies are installed:
```bash
pip install -r requirements.txt
```
*(Added `pytest-benchmark`, `psutil`, and `scikit-learn` for accurate profiling and evaluation metrics).*

## Structure Overview
- **`modules_benchmark/`**: Isolated module-level benchmarks measuring micro-latencies, Disk I/O, and CPU times. 
- **`project_bench_mark/`**: End-to-end RAG system evaluation measuring end-user latency, RAM/VRAM utilization, and retrieval metrics (Precision@K, Recall@K, NDCG, Hallucination checks).
- **`bench_mark.md`**: Found in each directory to log and store benchmark outputs.

## How to Run Benchmarks

### 1. Run All Benchmarks
To run the full suite using `pytest-benchmark`:
```bash
python -m pytest bench_marking/ --benchmark-only --benchmark-autosave
```

### 2. Module-Level Benchmarks
To benchmark the data layer (Disk I/O, Insertion Latency):
```bash
python -m pytest bench_marking/modules_benchmark/data_layer/ -v --benchmark-only > bench_marking/modules_benchmark/data_layer/bench_mark.md
```

To benchmark the retrieval layer:
```bash
python -m pytest bench_marking/modules_benchmark/retrieval_layer/ -v --benchmark-only > bench_marking/modules_benchmark/retrieval_layer/bench_mark.md
```

### 3. Project-Level (End-to-End RAG) Benchmarks
To evaluate end-to-end metrics like NDCG, Precision@K, RAM usage, and long-context accuracy:
```bash
python -m pytest bench_marking/project_bench_mark/ -v -s > bench_marking/project_bench_mark/bench_mark.md
```
*(Note: Use `-s` to capture the stdout of custom RAM profilers and metric calculations printed during the test).*
