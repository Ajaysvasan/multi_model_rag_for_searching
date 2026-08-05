============================= test session starts ==============================
platform linux -- Python 3.12.12, pytest-9.1.1, pluggy-1.6.0 -- /home/ajay/.conda/envs/rag_env/bin/python3
cachedir: .pytest_cache
benchmark: 5.2.3 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
rootdir: /home/ajay/Documents/multi_model_rag_for_searching/backend
plugins: anyio-4.12.1, md-0.2.0, benchmark-5.2.3
collecting ... collected 1 item

bench_marking/modules_benchmark/AdpaterModule/test_benchmark_AdpaterModule.py::test_benchmark_AdpaterModule PASSED [100%]


-------------------------------------------------- benchmark: 1 tests -------------------------------------------------
Name (time in ms)                   Min     Max    Mean  StdDev  Median     IQR  Outliers       OPS  Rounds  Iterations
-----------------------------------------------------------------------------------------------------------------------
test_benchmark_AdpaterModule     1.0112  1.5173  1.0785  0.0497  1.0561  0.0132   138;173  927.1822     877           1
-----------------------------------------------------------------------------------------------------------------------

Legend:
  Outliers: 1 Standard Deviation from Mean; 1.5 IQR (InterQuartile Range) from 1st Quartile and 3rd Quartile.
  OPS: Operations Per Second, computed as 1 / Mean
============================== 1 passed in 1.96s ===============================
