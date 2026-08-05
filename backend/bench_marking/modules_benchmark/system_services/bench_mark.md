============================= test session starts ==============================
platform linux -- Python 3.12.12, pytest-9.1.1, pluggy-1.6.0 -- /home/ajay/.conda/envs/rag_env/bin/python3
cachedir: .pytest_cache
benchmark: 5.2.3 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
rootdir: /home/ajay/Documents/multi_model_rag_for_searching/backend
plugins: anyio-4.12.1, md-0.2.0, benchmark-5.2.3
collecting ... collected 1 item

bench_marking/modules_benchmark/system_services/test_benchmark_system_services.py::test_benchmark_system_services PASSED [100%]


--------------------------------------------------- benchmark: 1 tests --------------------------------------------------
Name (time in ms)                     Min     Max    Mean  StdDev  Median     IQR  Outliers       OPS  Rounds  Iterations
-------------------------------------------------------------------------------------------------------------------------
test_benchmark_system_services     5.0380  5.4473  5.1888  0.0768  5.1742  0.0946      61;1  192.7232     192           1
-------------------------------------------------------------------------------------------------------------------------

Legend:
  Outliers: 1 Standard Deviation from Mean; 1.5 IQR (InterQuartile Range) from 1st Quartile and 3rd Quartile.
  OPS: Operations Per Second, computed as 1 / Mean
============================== 1 passed in 2.02s ===============================
