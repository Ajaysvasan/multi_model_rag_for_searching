# Backend Architecture

A local-first, multi-modal Retrieval-Augmented Generation service. Everything —
embeddings, vector search, reranking, and language-model inference — runs on the
user's own machine. No document text and no query ever leaves the host.

---

## 1. The problem

General-purpose chat assistants cannot answer questions about *your* files, and
uploading those files to a hosted model is often not an option: medical records,
internal reports, and personal archives cannot leave the building. The obvious
workaround — full-text search — fails because people ask questions
("what raises breast cancer risk?") rather than supply keywords, and because the
answer is usually spread across several documents in several formats.

This backend solves four problems at once:

| Problem | Approach |
|---|---|
| Documents arrive as PDF, DOCX, TXT, images, and audio | An ingestion pipeline that normalises every format into text, OCRing images and transcribing audio |
| Questions are semantic, not lexical | Sentence-transformer embeddings + FAISS HNSW approximate nearest-neighbour search |
| Retrieved passages are only *approximately* relevant | A cross-encoder reranker and a keyword-plus-embedding validator downstream of the ANN search |
| Language models invent facts and sources | Generation constrained to retrieved passages, with inline `[n]` citations filtered to the passages the model actually referenced |

The non-negotiable property is **answers must be traceable**. Every claim carries
a citation resolving to a specific chunk of a specific file on disk.

---

## 2. Architecture

### 2.1 Request lifecycle

```
                 ┌──────────────────────────────────────────────┐
  HTTP  ────────▶│  main.py  (FastAPI)                          │
  /query         │  authenticate → resolve user → build engine  │
                 └───────────────────┬──────────────────────────┘
                                     │
                 ┌───────────────────▼──────────────────────────┐
                 │  retrieval_layer.QueryProcessing             │
                 │  strip filler phrases, expand with history   │
                 └───────────────────┬──────────────────────────┘
                                     │
                 ┌───────────────────▼──────────────────────────┐
                 │  retrieval_layer.RetrievalEngine             │
                 │                                              │
                 │   1. cache_layer      topic cache lookup     │
                 │   2. history_layer    embedding-similar reuse│
                 │   3. data_layer.hnsw  FAISS ANN fallback     │
                 │   4. reranking        cross-encoder rerank   │
                 │   5. validation_layer relevance gate + retry │
                 └───────────────────┬──────────────────────────┘
                                     │  passages
                 ┌───────────────────▼──────────────────────────┐
                 │  generation_layer                            │
                 │  budget context → prompt → LLM → citations   │
                 │      ├── LlamaGenerator  (llama-cpp-python)  │
                 │      └── MmapGenerator   (C++ llm_backend)   │
                 └───────────────────┬──────────────────────────┘
                                     │
                          {answer, sources[]}
```

Retrieval is a three-stage fallback chain, cheapest first. A topic-cache hit
avoids embedding entirely; a history hit reuses a previous query's chunk set;
only a miss on both reaches the ANN index. Measured on a 20-core CPU, the whole
retrieval path costs ~39 ms — under 0.2% of a query. Generation dominates.

### 2.2 Storage

Two independent backends exist because the project supports two front ends:

| | TUI (`agent.py`) | Server (`main.py`) |
|---|---|---|
| Chunk metadata | SQLite (`data_layer/chunkstore`) | PostgreSQL (`data_models`) |
| Vector index | one FAISS index | one FAISS index **per user** |
| Cache | `cache_layer` L1/L2/L3, persisted | `AdpaterModule` → PostgreSQL |
| History | `history_layer`, persisted | in-memory per process |
| Isolation | single user | `user_id` on every row and index |

The server reaches the shared retrieval code through thin adapters in
`AdpaterModule/`, which present the PostgreSQL stores using the same interface
the SQLite implementations expose.

> **Known gap.** Two of those adapters are stubs. `cache_topics` has no column
> for chunk IDs, so `_UserCacheAdapter.lookup()` always returns `None` and the
> server takes the ANN path on every query; server-side history is per-process
> and lost on restart. The interfaces are correct — the persistence is not
> finished. See [`AdpaterModule.md`](AdpaterModule/AdpaterModule.md).

### 2.3 Inference

Two interchangeable generator backends, selected by `Config`:

- **`LlamaGenerator`** — in-process `llama-cpp-python`. Reads the chat template
  from the GGUF, so it works with any model. The default.
- **`MmapGenerator`** — talks to the standalone C++ `llm_backend` worker over a
  length-prefixed pipe. The model is `mmap`ed in a separate process, keeping the
  API server's own RSS low and isolating a model crash from the web service. It
  has no chat template of its own, so `Config.PROMPT_TEMPLATE` must match the
  model.

---

## 3. Layer reference

Each layer carries two documents in its own directory: a design note explaining
*why* it exists and how it works, and an API reference with runnable examples.

| Layer | Design | API |
|---|---|---|
| Retrieval orchestration | [retrieval_layer.md](retrieval_layer/retrieval_layer.md) | [API](retrieval_layer/retrieval_layer_API_DOCS.md) |
| Answer generation | [generation_layer.md](generation_layer/generation_layer.md) | [API](generation_layer/generation_layer_API_DOCS.md) |
| C++ inference worker | [llm_backend.md](llm_backend/llm_backend.md) | [API](llm_backend/llm_backend_API_DOCS.md) |
| Ingestion & chunking | [data_layer.md](data_layer/data_layer.md) | [API](data_layer/data_layer_API_DOCS.md) |
| Three-tier topic cache | [cache_layer.md](cache_layer/cache_layer.md) | [API](cache_layer/cache_layer_API_DOCS.md) |
| Conversation history | [history_layer.md](history_layer/history_layer.md) | [API](history_layer/history_layer_API_DOCS.md) |
| Cross-encoder reranking | [reranking.md](reranking/reranking.md) | [API](reranking/reranking_API_DOCS.md) |
| Relevance validation | [validation_layer.md](validation_layer/validation_layer.md) | [API](validation_layer/validation_layer_API_DOCS.md) |
| Auth & hashing | [security_layer.md](security_layer/security_layer.md) | [API](security_layer/security_layer_API_DOCS.md) |
| ORM models | [data_models.md](data_models/data_models.md) | [API](data_models/data_models_API_DOCS.md) |
| Declarative base | [db.md](db/db.md) | [API](db/db_API_DOCS.md) |
| PG ↔ engine adapters | [AdpaterModule.md](AdpaterModule/AdpaterModule.md) | [API](AdpaterModule/AdpaterModule_API_DOCS.md) |
| Composition & startup | [system_services.md](system_services/system_services.md) | [API](system_services/system_services_API_DOCS.md) |
| Terminal UI commands | [TUI_services.md](TUI_services/TUI_services.md) | [API](TUI_services/TUI_services_API_DOCS.md) |
| Corpus scraper | [wikipedia_scraper.md](wikipedia_scraper/wikipedia_scraper.md) | [API](wikipedia_scraper/wikipedia_scraper_API_DOCS.md) |

---

## 4. Setup

Three routes, in order of preference. Pick one.

### 4.1 Docker (recommended)

Brings up PostgreSQL and the API together; nothing but Docker is required on the
host.

```bash
git clone <repository-url> && cd multi_model_rag_for_searching

cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste as JWT_SECRET_KEY

# The GGUF is not baked into the image (1.6-4.4 GB). Fetch it once:
python backend/download_model.py

docker compose up --build -d db backend
docker compose logs -f backend        # wait for the model to load
curl http://localhost:8000/docs
```

`./backend/models` is mounted into the container, so the model is downloaded
once and shared. Add the Electron UI with
`docker compose --profile desktop up frontend` on a machine with an X display.

**GPU.** Build the worker with CUDA and switch the runtime stage to a CUDA base
image, then run with `--gpus all`:

```bash
docker compose build --build-arg GGML_CUDA=ON backend
```

### 4.2 Conda

```bash
conda create -n rag_env python=3.12 -y
conda activate rag_env

cd backend
pip install -r requirements.txt

cp .env.example .env      # point DB_HOST at your PostgreSQL instance
python download_model.py

uvicorn main:app --host 0.0.0.0 --port 8000
```

You need a reachable PostgreSQL with the `uuid-ossp` extension enabled:

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

**GPU.** The PyPI `llama-cpp-python` wheel is CPU-only. Confirm with:

```bash
python -c "import llama_cpp; print(llama_cpp.llama_supports_gpu_offload())"
```

`False` means CPU. Building a CUDA wheel needs no root if the toolkit goes in
the environment:

```bash
# nvcc 12.9 rejects host compilers newer than gcc 14, so bring gcc 13 along
conda install -n rag_env -y -c nvidia -c conda-forge "cuda-toolkit=12.9" "gxx_linux-64=13"

# CMAKE_CUDA_ARCHITECTURES must match the card:
#   86 = Ampere (RTX 30xx)  89 = Ada (RTX 40xx)  120 = Blackwell (RTX 50xx)
# `nvidia-smi --query-gpu=compute_cap --format=csv` reports e.g. 12.0 -> 120
CUDAHOSTCXX="$CONDA_PREFIX/bin/x86_64-conda-linux-gnu-g++" \
CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=120" \
  pip install --force-reinstall --no-cache-dir --no-binary llama-cpp-python llama-cpp-python
```

Afterwards the loader logs `GPU offload enabled` instead of a CPU warning.

> `pip --force-reinstall` may upgrade `numpy` past what `numba` (and therefore
> `openai-whisper`) accepts. Run `pip check` afterwards; `pip install
> "numpy<2.4"` restores compatibility.

### 4.3 Native Python

Same as conda, using the standard library's virtual environments. Python 3.11+.

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python download_model.py
uvicorn main:app --host 0.0.0.0 --port 8000
```

System packages the Python wheels expect: `tesseract-ocr` (image OCR), `ffmpeg`
(audio decoding), plus `build-essential` and `cmake` if any dependency has to
compile.

### 4.4 The C++ worker (optional)

Only needed to use `MmapGenerator`.

```bash
cd backend
git clone --depth 1 --branch b8057 https://github.com/ggml-org/llama.cpp.git third_party/llama.cpp

cmake -S llm_backend -B llm_backend/build -DCMAKE_BUILD_TYPE=Release
cmake --build llm_backend/build -j
ctest --test-dir llm_backend/build --output-on-failure
```

The binary is copied to `backend/bin/llm_backend`, where `Config.BIN_PATH`
expects it. Add `-DGGML_CUDA=ON` for GPU.

---

## 5. Configuration

All tuning lives in `config.py`; secrets live in `.env` (never committed).

| Setting | Default | Effect |
|---|---|---|
| `N_CTX` | 4096 | Context window. Costs KV cache, which moves to VRAM when offloading. |
| `N_BATCH` | 512 | Prompt-evaluation batch size. |
| `N_GPU_LAYERS` | -1 | -1 offloads everything the backend accepts; 0 forces CPU. |
| `MAX_NEW_TOKENS` | 256 | Generation cap; generation still stops at EOS. |
| `MAX_CONTEXT_CHUNKS` | 5 | Passages offered to the model. |
| `CHUNK_CHAR_LIMIT` | 1000 | Per-passage truncation. Raising it grows prefill. |
| `CTX_SAFETY_MARGIN` | 192 | Tokens withheld so the prompt cannot crowd out the answer. |
| `ANN_TOP_K` | 10 | ANN candidates (doubled before reranking). |
| `PROMPT_TEMPLATE` | model-specific | `zephyr` / `mistral` / `plain`, for the C++ worker only. |

---

## 6. Testing

```bash
pytest test/ -v                                        # Python suites
pytest bench_marking/ -v -s                            # benchmarks
ctest --test-dir llm_backend/build --output-on-failure # C++ suites
```

The C++ engine suite reports *Skipped* rather than failing when no `.gguf` is
present, so a checkout without models still builds and tests green.

---

## 7. API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/auth/register/` | Create an account, returns access + refresh tokens |
| `POST` | `/auth/login/` | Exchange credentials for tokens |
| `POST` | `/auth/refresh/` | Mint a new access token from a refresh token |
| `POST` | `/upload` | Ingest files into the caller's index |
| `POST` | `/query` | Ask a question, returns `{response, sources[]}` |

Interactive documentation is served at `/docs`.

---

## 8. Known gaps

Recorded here so they are not rediscovered as surprises:

- **Server cache and history are stubs.** See §2.2. Retrieval still works; it
  just always takes the slow path.
- **`/query` passes the user ID as the session ID.** `PgConversationMemory`
  looks that up as a `history_sessions` primary key, never matches, and creates
  a new session row per turn — so multi-turn context is not retained on the
  server path and the table grows unboundedly.
- **`/speech-query` does not exist.** The Electron client calls it; only the
  ingestion half of the audio pipeline is wired up.
- **`/upload` accepts arbitrary host paths.** Acceptable for a single-user
  desktop deployment, not for a shared server.
- **Generation is single-threaded.** One `Llama` instance is shared across a
  thread pool with no lock; concurrent requests are unsafe. `MmapGenerator`
  sidesteps this by isolating inference in its own process.
