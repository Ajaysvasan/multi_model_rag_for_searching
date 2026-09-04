# generation_layer — API reference

[← Back to BACKEND.md](../BACKEND.md) · [Design notes](generation_layer.md)

## Choosing a backend

```python
from generation_layer.generator import LlamaGenerator, MmapGenerator, AnswerGenerator

gen = LlamaGenerator()   # in-process, reads the chat template from the GGUF
gen = MmapGenerator()    # C++ worker; needs bin/llm_backend and PROMPT_TEMPLATE
gen = AnswerGenerator()  # platform alias: MmapGenerator on Linux/macOS
```

## Generating an answer

```python
from generation_layer.generator import LlamaGenerator

gen = LlamaGenerator()
gen.load_model(show_progress=True)      # optional; generate() loads on demand

chunks = [
    {
        "chunk_id": "a1",
        "chunk_text": "Risk factors include obesity, lack of exercise and alcohol.",
        "source_path": "/docs/risk.pdf",
        "modality": "text",
        "start_offset": 0,
        "end_offset": 61,
    },
]

result = gen.generate(
    query="What are the risk factors?",
    chunks=chunks,
    include_sources=True,
    max_new_tokens=256,          # defaults to Config.MAX_NEW_TOKENS
    temperature=0.1,             # defaults to Config.GEN_TEMPERATURE
    conversation_context=[
        {"role": "user", "content": "Tell me about breast cancer."},
        {"role": "assistant", "content": "Breast cancer develops from breast tissue."},
    ],
)

print(result.success, result.answer)
for c in result.citations:
    print(f"[{c.citation_id}] {c.source_path}: {c.chunk_text[:60]}")
```

### `GenerationResult`

| Field | Type | Notes |
|---|---|---|
| `answer` | `str` | Cleaned text |
| `citations` | `list[Citation]` | Only the passages the model actually cited |
| `raw_response` | `str` | Pre-cleaning output, for debugging |
| `model_used` | `str` | Model identifier |
| `tokens_used` | `int` | Currently always `0` — not populated |
| `success` | `bool` | |
| `error` | `str \| None` | |

### `Citation`

`citation_id` (the `n` in `[n]`), `chunk_id`, `source_path`, `chunk_text`
(first 200 chars), `start_offset`, `end_offset`, `relevance_score`.

## Behaviour on edge cases

| Input | Result |
|---|---|
| `chunks=[]` | `success=True`, "I couldn't find any relevant information.", no citations |
| All chunks have empty text | `success=False`, `error="All chunks have empty text"` |
| Every chunk under 50 characters | Returns them as a bullet list rather than prompting the model |
| Model refuses | `success=True`, refusal text, **zero** citations |
| Prompt exceeds the budget | Excess passages dropped, logged; generation proceeds |

## Prompt helpers

```python
from generation_layer.prompts import (
    SYSTEM_PROMPT, estimate_tokens, format_context_for_generation, wrap_prompt,
)

estimate_tokens("some text")        # cheap pre-tokenizer estimate

context = format_context_for_generation(
    chunks,
    include_source=True,
    max_chunks=5,
    token_budget=3482,              # None keeps the old unbounded behaviour
    char_limit=1000,
)

# Only needed for the C++ worker; llama-cpp-python does this itself.
prompt = wrap_prompt(SYSTEM_PROMPT, user_message, template="mistral")
```

`wrap_prompt` templates: `"mistral"` (`[INST] <<SYS>>…`), `"zephyr"`
(`<|system|>…<|user|>…<|assistant|>`), `"plain"`. It defaults to
`Config.PROMPT_TEMPLATE`. **A mismatch degrades answers silently** — the model
still produces fluent text, it just stops following instructions.

## Static helpers

```python
LlamaGenerator._clean_response("The answer.\nReferences:\n[1] Fake")  # "The answer."
LlamaGenerator._is_refusal("I could not find relevant information.")  # True
LlamaGenerator._is_refusal("Mammography is primary [1]. The passages do not mention MRI.")  # False
LlamaGenerator._extract_cited_indices("A [1] and B [3].")             # {1, 3}
```

`_is_refusal` inspects **only the first sentence**, so an answer that mentions
what the sources lack partway through is not mistaken for a refusal.

## `MmapGenerator` lifecycle

```python
gen = MmapGenerator(
    model_path="models",                      # dir or full file path
    backend_path="bin/llm_backend",
)
gen.load_model()          # spawns the worker, waits for READY
result = gen.generate(query="...", chunks=chunks)
gen.close()               # terminate; also runs from __del__
```

The worker is spawned on first use and reused across calls; a dead worker is
respawned on the next request. `close()` is idempotent.

## Configuration

Read from `config.py` at call time, so overriding `Config` before constructing a
generator works:

`GENERATION_MODEL`, `GENERATION_MODEL_FILE`, `MODELS_DIR`, `N_CTX`, `N_BATCH`,
`N_THREADS`, `N_GPU_LAYERS`, `MAX_NEW_TOKENS`, `GEN_TEMPERATURE`,
`MAX_CONTEXT_CHUNKS`, `CHUNK_CHAR_LIMIT`, `CTX_SAFETY_MARGIN`,
`PROMPT_TEMPLATE`, `USE_LOCAL_MODEL`, `OFFLINE_MODE`, `BIN_PATH`.

### Verifying GPU offload

```python
import llama_cpp
llama_cpp.llama_supports_gpu_offload()   # False -> CPU-only wheel
```

Setting `N_GPU_LAYERS = -1` on a CPU-only build does nothing; the loader logs a
warning rather than silently claiming acceleration.
