============================= test session starts ==============================
platform linux -- Python 3.12.12, pytest-9.1.1, pluggy-1.6.0 -- /home/ajay/.conda/envs/rag_env/bin/python3
cachedir: .pytest_cache
benchmark: 5.2.3 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
rootdir: /home/ajay/Documents/multi_model_rag_for_searching/backend
plugins: anyio-4.12.1, md-0.2.0, benchmark-5.2.3
collecting ... collected 24 items

test/project_testing/test_project.py::test_config_uses_mistral_7b PASSED [  4%]
test/project_testing/test_project.py::test_config_default_model_matches PASSED [  8%]
test/project_testing/test_project.py::test_model_file_exists PASSED      [ 12%]
test/project_testing/test_project.py::test_model_file_size PASSED        [ 16%]
test/project_testing/test_project.py::test_generation_layer_imports PASSED [ 20%]
test/project_testing/test_project.py::test_generator_classes_exist PASSED [ 25%]
test/project_testing/test_project.py::test_generation_result_dataclass PASSED [ 29%]
test/project_testing/test_project.py::test_citation_dataclass PASSED     [ 33%]
test/project_testing/test_project.py::test_clean_response_removes_references PASSED [ 37%]
test/project_testing/test_project.py::test_clean_response_removes_urls PASSED [ 41%]
test/project_testing/test_project.py::test_is_refusal_true PASSED        [ 45%]
test/project_testing/test_project.py::test_is_refusal_false PASSED       [ 50%]
test/project_testing/test_project.py::test_generate_empty_chunks PASSED  [ 54%]
test/project_testing/test_project.py::test_generate_short_chunks PASSED  [ 58%]
test/project_testing/test_project.py::test_config_embedding_model PASSED [ 62%]
test/project_testing/test_project.py::test_config_reranker_model PASSED  [ 66%]
test/project_testing/test_project.py::test_download_model_script_importable PASSED [ 70%]
test/project_testing/test_project.py::test_stress_1m_token_context_allocation PASSED [ 75%]
test/project_testing/test_project.py::test_stress_5m_token_context_allocation PASSED [ 79%]
test/project_testing/test_project.py::test_stress_rapid_generation_results PASSED [ 83%]
test/project_testing/test_project.py::test_stress_large_chunk_list PASSED [ 87%]
test/project_testing/test_project.py::test_stress_clean_response_large_input PASSED [ 91%]
test/project_testing/test_project.py::test_stress_concurrent_citation_creation PASSED [ 95%]
test/project_testing/test_project.py::test_stress_repeated_refusal_checks PASSED [100%]

=============================== warnings summary ===============================
test/project_testing/test_project.py::test_clean_response_removes_references
test/project_testing/test_project.py::test_clean_response_removes_urls
test/project_testing/test_project.py::test_is_refusal_true
test/project_testing/test_project.py::test_is_refusal_false
test/project_testing/test_project.py::test_generate_empty_chunks
test/project_testing/test_project.py::test_generate_short_chunks
test/project_testing/test_project.py::test_stress_clean_response_large_input
test/project_testing/test_project.py::test_stress_repeated_refusal_checks
  /home/ajay/.conda/envs/rag_env/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function LlamaGenerator.__del__ at 0x7fd67cbe8f40>
  
  Traceback (most recent call last):
    File "/home/ajay/Documents/multi_model_rag_for_searching/backend/generation_layer/generator.py", line 363, in __del__
      if self.model is not None:
         ^^^^^^^^^^
  AttributeError: 'LlamaGenerator' object has no attribute 'model'
  
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 24 passed, 8 warnings in 0.10s ========================
