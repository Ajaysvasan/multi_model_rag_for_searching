============================= test session starts ==============================
platform linux -- Python 3.12.12, pytest-9.1.1, pluggy-1.6.0 -- /home/ajay/.conda/envs/rag_env/bin/python3
cachedir: .pytest_cache
rootdir: /home/ajay/Documents/multi_model_rag_for_searching/backend
plugins: anyio-4.12.1, md-0.2.0
collecting ... collected 2 items

test/project_testing/test_project.py::test_project_main_imports PASSED   [ 50%]
test/project_testing/test_project.py::test_project_configuration PASSED  [100%]

=============================== warnings summary ===============================
test/project_testing/test_project.py::test_project_main_imports
  /home/ajay/.conda/envs/rag_env/lib/python3.12/site-packages/passlib/utils/__init__.py:854: DeprecationWarning: 'crypt' is deprecated and slated for removal in Python 3.13
    from crypt import crypt as _crypt

test/project_testing/test_project.py::test_project_main_imports
  /home/ajay/.conda/envs/rag_env/lib/python3.12/site-packages/pydub/utils.py:14: DeprecationWarning: 'audioop' is deprecated and slated for removal in Python 3.13
    import audioop

test/project_testing/test_project.py::test_project_main_imports
  /home/ajay/.conda/envs/rag_env/lib/python3.12/site-packages/torch/cuda/__init__.py:184: UserWarning: CUDA initialization: Unexpected error from cudaGetDeviceCount(). Did you run some cuda functions before calling NumCudaDevices() that might have already set an error? Error 304: OS call failed or operation not supported on this OS (Triggered internally at /pytorch/c10/cuda/CUDAFunctions.cpp:119.)
    return torch._C._cuda_getDeviceCount() > 0

test/project_testing/test_project.py::test_project_main_imports
  /home/ajay/.conda/envs/rag_env/lib/python3.12/site-packages/torchao/dtypes/floatx/__init__.py:5: DeprecationWarning: Importing from torchao.dtypes.floatx.floatx_tensor_core_layout is deprecated. Please use 'from torchao.prototype.dtypes.floatx.floatx_tensor_core_layout import ...' instead. This import path will be removed in a future torchao release. Please check issue: https://github.com/pytorch/ao/issues/2752 for more details. 
    from .floatx_tensor_core_layout import (

test/project_testing/test_project.py::test_project_main_imports
  /home/ajay/.conda/envs/rag_env/lib/python3.12/site-packages/torchao/dtypes/uintx/__init__.py:1: DeprecationWarning: Importing from torchao.dtypes.uintx.dyn_int8_act_int4_wei_cpu_layout is deprecated. Please use 'from torchao.prototype.dtypes import Int8DynamicActInt4WeightCPULayout' instead. This import path will be removed in a future release of torchao. See https://github.com/pytorch/ao/issues/2752 for more details.
    from .dyn_int8_act_int4_wei_cpu_layout import (

test/project_testing/test_project.py::test_project_main_imports
  /home/ajay/.conda/envs/rag_env/lib/python3.12/site-packages/torchao/dtypes/uintx/__init__.py:10: DeprecationWarning: Importing from torchao.dtypes.uintx.marlin_qqq_tensor is deprecated. Please use 'from torchao.prototype.dtypes import MarlinQQQLayout, MarlinQQQTensor' instead. This import path will be removed in a future release of torchao. See https://github.com/pytorch/ao/issues/2752 for more details.
    from .marlin_qqq_tensor import (

test/project_testing/test_project.py::test_project_main_imports
  /home/ajay/.conda/envs/rag_env/lib/python3.12/site-packages/torchao/dtypes/uintx/__init__.py:30: DeprecationWarning: Importing from torchao.dtypes.uintx.uintx_layout is deprecated. Please use 'from torchao.prototype.dtypes import UintxLayout, UintxTensor' instead. This import path will be removed in a future release of torchao. See https://github.com/pytorch/ao/issues/2752 for more details.
    from .uintx_layout import (

test/project_testing/test_project.py::test_project_main_imports
  /home/ajay/.conda/envs/rag_env/lib/python3.12/site-packages/torchao/dtypes/__init__.py:25: DeprecationWarning: Importing BlockSparseLayout from torchao.dtypes is deprecated. Please use 'from torchao.prototype.dtypes import BlockSparseLayout' instead. This import path will be removed in a future torchao release. Please check issue: https://github.com/pytorch/ao/issues/2752 for more details. 
    from .uintx.block_sparse_layout import BlockSparseLayout

test/project_testing/test_project.py::test_project_main_imports
  /home/ajay/.conda/envs/rag_env/lib/python3.12/site-packages/torchao/dtypes/__init__.py:26: DeprecationWarning: Importing from torchao.dtypes is deprecated. Please use 'from torchao.prototype.dtypes import CutlassInt4PackedLayout' instead. This import path will be removed in a future torchao release. Please check issue: https://github.com/pytorch/ao/issues/2752 for more details. 
    from .uintx.cutlass_int4_packed_layout import CutlassInt4PackedLayout

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 2 passed, 9 warnings in 6.24s =========================
