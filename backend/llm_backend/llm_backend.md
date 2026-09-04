# llm_backend — C++ inference worker

[← Back to BACKEND.md](../BACKEND.md) · [API reference](llm_backend_API_DOCS.md)

A standalone process that loads a GGUF model through llama.cpp and answers
prompts over a pipe. The Python side talks to it via `MmapGenerator`.

## Why it exists

`llama-cpp-python` already runs models in-process, so a separate binary needs a
reason. There are three:

1. **RSS isolation.** The model is `mmap`ed, so pages are faulted in on demand
   and the OS can evict them under pressure. The API server's own resident set
   stays small, and a 4 GB model does not sit inside the web process.
2. **Crash isolation.** A CUDA fault or an OOM in inference kills the worker,
   not the FastAPI service. The parent notices the closed pipe and can respawn.
3. **The GIL.** Inference in-process holds Python's interpreter lock for long
   stretches. A separate process sidesteps that entirely.

The cost is a serialisation boundary and a chat template that must be applied by
hand, since the worker does not read the GGUF's template metadata.

## Design

Three translation units with one responsibility each:

```
main.cpp        process concerns: argv, signals, the read→generate→write loop
  ├── protocol  framing only. No llama.cpp dependency, so it unit-tests in ms
  └── engine    all llama.cpp interaction. No I/O.
```

The split is what makes the tests cheap: `test_protocol` exercises every framing
edge case without loading a model, and only `test_engine` needs a GGUF (and
skips cleanly when none is present).

### Memory ownership

Every llama.cpp handle is owned by a `unique_ptr` with a matching deleter, and
`llama_batch` — which allocates several parallel arrays — is owned by a
`BatchGuard` scope object:

| Resource | Owner | Released by |
|---|---|---|
| `llama_model*` | `unique_ptr<…, ModelDeleter>` | `llama_model_free` |
| `llama_context*` | `unique_ptr<…, ContextDeleter>` | `llama_free` |
| `llama_sampler*` | `unique_ptr<…, SamplerDeleter>` | `llama_sampler_free` |
| `llama_batch` | `BatchGuard` | `llama_batch_free` |
| backend globals | `BackendGuard` | `llama_backend_free` |

There is no raw `new`/`delete` and no manual free that an early return can skip.
This matters because the decode paths have several failure exits; the previous
single-file version allocated a batch per generated token and freed it on only
some of them.

`BackendGuard` is declared in `main` *before* the `Engine`, so destruction order
guarantees `llama_backend_free` runs after the model is gone.

**Verification.** 40 consecutive requests through the real pipe moved resident
memory by **0.0 KiB**. `sanitizers` are wired up behind
`-DLLM_BACKEND_ASAN=ON` for machines that have `libasan` installed.

### What changed from the original

| Before | Now | Why |
|---|---|---|
| `llama_free` + `llama_init_from_model` **inside the request loop** | `llama_memory_clear` on the existing context | Rebuilt every buffer and discarded the warm-up decode on every single request |
| `n_gpu_layers` never set (default 0) | `mparams.n_gpu_layers` from config | The worker ran on CPU even against a GPU build |
| Hand-rolled argmax over the full vocabulary | `llama_sampler` chain | Ignored temperature, top-p and repeat-penalty entirely; could not stop on non-EOS end-of-generation tokens |
| `llama_batch_init`/`free` per generated token | one reused single-token batch | An allocation pair per token |
| Token buffer guessed as `prompt.size() + 8` | two-pass `llama_tokenize` | The guess over-allocates for ASCII and is not guaranteed correct for other scripts |
| `n_ctx` hardcoded 8192 (Python used 2048) | `LLM_N_CTX`, defaulting to match `Config.N_CTX` | The two halves of the system disagreed |
| Everything in one 234-line file | `engine` / `protocol` / `main` | Nothing was testable without a model |

### Generation flow

`Engine::Generate` clears the KV cache and resets the sampler, so requests are
independent without a context rebuild. The prompt is decoded in `n_batch`-sized
slices, requesting logits only for the final token. Generation is then clamped
to `min(max_new_tokens, n_ctx − prompt_tokens)`, which is why an over-long
prompt is rejected up front rather than overrunning the cache mid-answer.

A decode failure part-way through generation keeps the partial answer rather
than discarding it — a truncated answer is more useful than an error.

## Protocol

```
  parent ──▶  [uint32 LE length][UTF-8 prompt]   ──▶ worker
  parent ◀──  [uint32 LE length][UTF-8 reply]    ◀── worker
```

Little-endian, matching Python's `struct.pack("<I", n)`; a test asserts the byte
order so the two halves cannot drift. The worker prints `READY` on stdout once
loaded. A reply beginning `ERROR: ` signals failure — the request failed, but
the worker is still alive and the loop continues.

Frames larger than 64 MiB are refused rather than allocated, so a corrupt length
prefix cannot trigger a multi-gigabyte allocation.

## Limits

- **One request at a time.** A single context, no queue. Run several workers for
  concurrency.
- **No chat template.** The worker sees a finished prompt string;
  `Config.PROMPT_TEMPLATE` must match the model or quality degrades silently.
- **No streaming.** One request, one complete reply.
