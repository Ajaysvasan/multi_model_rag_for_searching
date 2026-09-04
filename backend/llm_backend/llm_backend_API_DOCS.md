# llm_backend — API reference

[← Back to BACKEND.md](../BACKEND.md) · [Design notes](llm_backend.md)

## Building

```bash
cd backend
cmake -S llm_backend -B llm_backend/build -DCMAKE_BUILD_TYPE=Release
cmake --build llm_backend/build -j
ctest --test-dir llm_backend/build --output-on-failure
```

The binary lands in `backend/bin/llm_backend`.

| CMake option | Default | Effect |
|---|---|---|
| `LLAMA_ROOT` | — | Path to a llama.cpp tree; otherwise `third_party/llama.cpp`, then `find_package` |
| `LLM_BACKEND_BUILD_TESTS` | `ON` | Build `test_protocol` and `test_engine` |
| `LLM_BACKEND_ASAN` | `OFF` | AddressSanitizer + UBSan (needs `libasan`) |
| `GGML_CUDA` | `OFF` | Passed through to llama.cpp for GPU support |

## Running

```bash
./bin/llm_backend models/mistral-7b-instruct-v0.2.Q4_K_M.gguf
```

Environment overrides (all optional):

| Variable | Default | Meaning |
|---|---|---|
| `LLM_N_GPU_LAYERS` | `-1` | Layers to offload; `-1` all, `0` CPU |
| `LLM_N_CTX` | `4096` | Context window |
| `LLM_N_THREADS` | `0` | CPU threads; `0` = hardware concurrency |
| `LLM_N_BATCH` | `512` | Prompt-evaluation batch size |
| `LLM_MAX_NEW_TOKENS` | `256` | Generation cap per request |
| `LLM_TEMPERATURE` | `0.1` | `<= 0` selects greedy sampling |
| `LLM_TOP_P` | `0.9` | Nucleus threshold |
| `LLM_TOP_K` | `20` | Top-k cutoff |
| `LLM_REPEAT_PENALTY` | `1.1` | `1.0` disables |
| `LLM_SEED` | llama default | RNG seed |

A malformed value falls back to the default rather than becoming `0`.

## Talking to it from Python

The supported client is `MmapGenerator`:

```python
from generation_layer.generator import MmapGenerator

gen = MmapGenerator()                    # paths come from Config
chunks = [{
    "chunk_id": "a1",
    "chunk_text": "Risk factors include obesity and alcohol consumption.",
    "source_path": "/docs/risk.pdf",
    "modality": "text",
}]

result = gen.generate(query="What are the risk factors?", chunks=chunks)
print(result.answer)                     # "... obesity ... alcohol ... [1]"
print([c.source_path for c in result.citations])
gen.close()                              # terminates the worker
```

The worker is spawned lazily on the first `generate()` and reused. If it dies,
the next call respawns it.

### Speaking the protocol directly

```python
import struct, subprocess

proc = subprocess.Popen(
    ["./bin/llm_backend", "models/model.gguf"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0,
)
assert proc.stdout.readline().decode().strip() == "READY"

def ask(prompt: str) -> str:
    payload = prompt.encode("utf-8")
    proc.stdin.write(struct.pack("<I", len(payload)))
    proc.stdin.write(payload)
    proc.stdin.flush()
    (n,) = struct.unpack("<I", proc.stdout.read(4))
    return proc.stdout.read(n).decode("utf-8", "replace")

reply = ask("[INST] What is 2 + 2? [/INST]")
if reply.startswith("ERROR: "):
    raise RuntimeError(reply)
print(reply)

proc.stdin.close()
proc.wait(timeout=10)
```

Closing stdin ends the loop and the process exits 0.

## C++ API

### `llm::EngineParams`

Configuration struct. `LoadParamsFromEnv(defaults)` layers `LLM_*` variables on
top of whatever you pass in.

### `llm::BackendGuard`

RAII for `llama_backend_init` / `llama_backend_free`. Construct one per process,
**before** any `Engine`, and let it outlive them.

### `llm::Engine`

```cpp
#include "engine.hpp"

llm::BackendGuard backend;        // must outlive every Engine

llm::EngineParams params;
params.model_path    = "models/model.gguf";
params.n_ctx         = 4096;
params.n_gpu_layers  = -1;
params.temperature   = 0.0f;      // greedy: reproducible
params = llm::LoadParamsFromEnv(params);

llm::Engine engine;
std::string error;
if (!engine.Load(params, error)) {
    std::cerr << "load failed: " << error << "\n";
    return 1;
}

const llm::GenerationResult r = engine.Generate("[INST] Hello [/INST]");
if (!r.ok) {
    std::cerr << "generate failed: " << r.error << "\n";
} else {
    std::cout << r.text << "\n"
              << r.prompt_tokens << " prompt, "
              << r.generated_tokens << " generated"
              << (r.hit_token_limit ? " (hit cap)" : " (stopped at EOG)")
              << "\n";
}
// No cleanup: every handle is released by destructors.
```

| Member | Notes |
|---|---|
| `Load(params, &error)` | `false` on failure, leaving the object unused |
| `Generate(prompt)` | Clears KV cache and resets the sampler first; requests are independent |
| `Tokenize(text, add_bos)` | Exposed for tests and prompt-length checks |
| `n_ctx()` | Effective context size, `0` when not loaded |
| `loaded()` | Whether `Load` succeeded |

`GenerationResult` carries `ok`, `text`, `error`, `prompt_tokens`,
`generated_tokens`, and `hit_token_limit` (stopped at the cap rather than at an
end-of-generation token).

`Engine` is move-only and **not** thread-safe — one context, one request at a
time. Use one `Engine` per thread, each with its own model handle, or run
several worker processes.

### `llm::Protocol`

```cpp
#include "protocol.hpp"

llm::Protocol proto(stdin, stdout);

std::string msg;
while (proto.ReadMessage(msg)) {
    if (!proto.WriteMessage("echo: " + msg)) break;
}
proto.WriteError("something went wrong");   // sends "ERROR: something went wrong"
```

`ReadMessage` returns `false` on EOF, a short read, or a length above
`llm::kMaxMessageBytes` (64 MiB), and leaves the output string untouched on
failure. The `FILE*` handles are borrowed, not owned.
