# Benchmarking Guide

This directory contains scripts and configurations for profiling the performance and accuracy of the Multi-Modal RAG backend.

## Prerequisites

Ensure your environment has the following benchmarking and metric libraries installed:
```bash
pip install pytest-benchmark psutil scikit-learn
```

## Benchmark Structure

The benchmarking suite is split into:

1. **`modules_benchmark/`**: Micro-benchmarks for individual components (e.g., FAISS search latency, Redis cache I/O, reranker throughput).
2. **`project_bench_mark/`**: Macro-benchmarks focusing on the entire RAG pipeline from query to response, evaluating the overall system behavior.

*Note: All benchmarks utilize the **Mistral-7B-Instruct-v0.2** model.*

## Running Benchmarks

### Running Module Benchmarks
To evaluate individual component speeds and memory usage:
```bash
pytest bench_marking/modules_benchmark/ -v -s
```

### Running Project Benchmarks
To evaluate end-to-end performance, accuracy, and system resilience:
```bash
pytest bench_marking/project_bench_mark/ -v -s
```

**Project benchmarks include:**
- **Citation Accuracy:** Measures how accurately the LLM cites the retrieved chunks using `scikit-learn` metrics.
- **Subsystem Toggle:** Tests the system's performance and accuracy when specific optional subsystems (like the 3-tier cache or cross-encoder reranker) are enabled vs. disabled. This highlights the architectural tradeoffs.
- **Stress Tests:** Measures throughput (queries per second) and resource utilization (`psutil` for RAM/CPU) under concurrent load.

### Generating Reports
To generate a markdown benchmark report summarizing the results:
```bash
pytest bench_marking/ -v --benchmark-json=bench_mark.json
# Depending on your CI/CD setup, you can parse the JSON into Markdown, or pipe terminal output:
pytest bench_marking/ -v > bench_mark.md
```

## Subsystem Toggle Benchmarks Concept
The "subsystem toggle" benchmarks are uniquely designed to isolate the impact of different pipeline stages. For instance, we benchmark a query flow with the semantic cache *on* versus *off*, or the reranker *on* versus *off*. This helps in calculating the exact latency cost and accuracy benefit of each stage, ensuring that adding complex components actually improves the overall user experience.
