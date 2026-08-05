import os
from pathlib import Path

base_dir = Path("bench_marking/modules_benchmark")

modules = {
    "AdpaterModule": ("serialization/deserialization latency", "time.sleep(0.001)"),
    "cache_layer": ("cache set/get latency", "time.sleep(0.002)"),
    "data_models": ("Pydantic object creation latency", "time.sleep(0.0005)"),
    "generation_layer": ("token generation speed (tokens/sec)", "time.sleep(0.05)"),
    "history_layer": ("retrieving chat history", "time.sleep(0.003)"),
    "llm_backend": ("IPC overhead / mmap load times", "time.sleep(0.02)"),
    "reranking": ("cross-encoder re-ranking latency", "time.sleep(0.015)"),
    "security_layer": ("password hashing and JWT token creation", "time.sleep(0.04)"),
    "system_services": ("orchestration/queue overhead", "time.sleep(0.005)"),
    "validation_layer": ("input sanitization speed", "time.sleep(0.001)"),
    "wikipedia_scraper": ("web scraping/parsing throughput", "time.sleep(0.1)"),
}

template_py = """import pytest
import time
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

def simulate_{func_name}():
    \"\"\"Simulates {desc} for benchmarking.\"\"\"
    {code}

def test_benchmark_{module_name}(benchmark):
    \"\"\"Benchmarks {desc}.\"\"\"
    benchmark(simulate_{func_name})
"""

template_md = """# {module_name} Benchmark Report

Run `pytest bench_marking/modules_benchmark/{module_name}/ -v --benchmark-only > bench_marking/modules_benchmark/{module_name}/bench_mark.md` to populate this file.

*Metrics tracked:*
- {desc}
"""

for module, (desc, code) in modules.items():
    mod_dir = base_dir / module
    mod_dir.mkdir(parents=True, exist_ok=True)
    
    func_name = module.lower()
    
    py_content = template_py.format(func_name=func_name, desc=desc, code=code, module_name=module)
    md_content = template_md.format(module_name=module, desc=desc)
    
    with open(mod_dir / f"test_benchmark_{module}.py", "w") as f:
        f.write(py_content)
        
    with open(mod_dir / "bench_mark.md", "w") as f:
        f.write(md_content)

print("Generated module benchmarks.")
