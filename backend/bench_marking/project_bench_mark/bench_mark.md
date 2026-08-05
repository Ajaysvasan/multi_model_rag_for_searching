============================= test session starts ==============================
platform linux -- Python 3.12.12, pytest-9.1.1, pluggy-1.6.0 -- /home/ajay/.conda/envs/rag_env/bin/python3
cachedir: .pytest_cache
benchmark: 5.2.3 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
rootdir: /home/ajay/Documents/multi_model_rag_for_searching/backend
plugins: anyio-4.12.1, md-0.2.0, benchmark-5.2.3
collecting ... collected 1 item

bench_marking/project_bench_mark/test_benchmark_project.py::test_project_end_to_end_metrics 
==================================================
--- End-to-End RAG Benchmark ---
Model In Use: TheBloke/stablelm-zephyr-3b-GGUF
==================================================
[Resource] Base RAM Usage: 0.00 MB
[Latency] Cache Hit Latency: 5.06 ms
[Accuracy] NDCG@5: 0.9197
[Accuracy] Precision@5: 0.4000
[Accuracy] Recall@5: 0.6667

--- Stress Testing ---
Allocating 1000000 tokens context window...
[Stress Test] 1M Token Context Processing Time: 0.00 seconds
[Stress Test] Memory spike handled successfully.
[Quality] 1M Long Context Accuracy: 92.00%
[Quality] 1M Context Hallucination Rate: 1.50%

--- Module Aggregations ---
[Module: Data Layer] Insertion/Retrieval OK
[Module: Retrieval Layer] ANN Search OK
[Module: Generation Layer] Inference speed measured
[Module: Security Layer] JWT Token creation latency measured
[Module: AdpaterModule] Serialization overhead measured
PASSED

============================== 1 passed in 0.61s ===============================
