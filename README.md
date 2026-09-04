# Multi-Model RAG for Searching

A local-first, multi-modal Retrieval-Augmented Generation system: an Electron
desktop client on top of a FastAPI backend that ingests your PDFs, DOCX files,
images, and audio, indexes them, and answers questions about them with inline
citations. Embeddings, vector search, reranking, and language-model inference
all run on the machine you start it on — no document text and no query leaves
the host.

---

## 1. The problem

General-purpose chat assistants cannot answer questions about *your* files, and
uploading those files to a hosted model is frequently not an option: medical
records, internal reports, and personal archives cannot leave the building. The
obvious local workaround — full-text search — fails for two reasons: people ask
questions ("what raises breast cancer risk?") rather than supply keywords, and
the answer is usually spread across several documents in several formats.

This project solves four problems at once:

| Problem | Approach |
|---|---|
| Documents arrive as PDF, DOCX, TXT, images, and audio | An ingestion pipeline that normalises every format into text, OCRing images and transcribing audio |
| Questions are semantic, not lexical | Sentence-transformer embeddings + FAISS HNSW approximate nearest-neighbour search |
| Retrieved passages are only *approximately* relevant | A cross-encoder reranker and a keyword-plus-embedding validator downstream of the ANN search |
| Language models invent facts and sources | Generation constrained to retrieved passages, with inline `[n]` citations filtered to the passages the model actually referenced |
| The data is private | Everything runs locally: local GGUF weights via `llama.cpp`, local FAISS index, local PostgreSQL |

The non-negotiable property is that **answers must be traceable**. Every claim
carries a citation that resolves to a specific chunk of a specific file on
disk, and clicking a source chip in the UI opens that file.

### What it is made of

```
Electron client  ──HTTP──▶  FastAPI  ──▶  retrieval  ──▶  generation
 (Frontend/)                (backend/)     cache → history → FAISS ANN
                                           → reranker → validator
                                                          │
                                            llama-cpp-python  or  C++ llm_backend
```

Retrieval is a three-stage fallback chain, cheapest first: a topic-cache hit
avoids embedding entirely, a history hit reuses a previous query's chunk set,
and only a miss on both reaches the ANN index. The full architecture, layer by
layer, is in [`backend/README.md`](./backend/README.md).

---

## 2. Benchmarks

All numbers below come from the real-data run recorded in
[`backend/bench_marking/project_bench_mark/benchmark.md`](./backend/bench_marking/project_bench_mark/benchmark.md)
(generated 2026-08-08). Every query, chunk, and embedding in that run is read
from the live database — there is no synthetic data in the pipeline
measurements. The exact configuration is in [§3](#3-benchmark-configuration).

### 2.1 Retrieval pipeline ablation

Each subsystem switched off in turn, same query, same corpus:

| Configuration | Latency (s) | NDCG | Precision@5 | Chunks retrieved |
|---|---|---|---|---|
| Full pipeline (cache + history + reranker + validator) | 0.0337 | 1.00 | 1.00 | 4 |
| Cache disabled | 0.0464 | 1.00 | 1.00 | 3 |
| History disabled | 0.0317 | 1.00 | 1.00 | 2 |
| Reranker disabled | 0.0245 | 1.00 | 1.00 | 2 |
| Validator disabled | 0.0250 | 1.00 | 1.00 | 2 |
| Cache + history disabled | 0.0304 | 1.00 | 1.00 | 3 |
| **Minimal pipeline (all off)** | **4.5284** | **0.98** | **0.75** | 4 |

Reading these honestly: the differences between the first six rows are tens of
milliseconds and sit inside run-to-run noise — no single optional subsystem is
worth much on its own. The result that matters is the last row. With the whole
fallback chain disabled, every query pays the cold embedding + ANN path:
**4.53 s versus 0.034 s, a ~134x slowdown**, and retrieval quality drops
(Precision@5 1.00 → 0.75). Retrieval is ~39 ms of a full query; generation
dominates everything else.

### 2.2 Answer quality and citations

Three organic queries, full pipeline, real LLM generation:

| Metric | Value |
|---|---|
| Average end-to-end generation time | 22.0 s |
| Citation precision | 1.00 |
| Citation recall (top-1) | 1.00 |
| Citation F1 | 1.00 |
| Citations emitted vs. chunks offered | 1.0 of 3.3 |

Precision 1.00 means every citation the model produced pointed at a real,
retrieved chunk — no invented sources. Recall 1.00 means the most relevant
chunk was cited every time. The model cites ~1 of the ~3 passages it is given,
which is selective rather than overfitted; a system gaming the metric would
cite everything.

### 2.3 Throughput and stress

| Test | Result |
|---|---|
| Embed 100 real chunks from the DB | 0.88 s |
| 20 consecutive `retrieve_enhanced()` calls | 4.83 s total, 0.242 s average |
| LLM generation over 5 DB chunks | 79.6 s |
| LLM generation over 25 DB chunks | 89.1 s |

### 2.4 Long-context behaviour

| Chunks | ~Tokens | Generation time (s) | RAM Δ (MB) |
|---|---|---|---|
| 5 | 149 | 105.9 | -454 |
| 10 | 245 | 46.1 | 0 |
| 25 | 553 | 30.2 | 0 |

Time does not grow with context here; the spread is dominated by how many
tokens the model chose to emit, and memory is flat, so the context budget in
`Config` is holding.

### 2.5 Memory

| Metric | Value |
|---|---|
| RSS before model load | 894 MB |
| RSS after model load | 8006 MB |
| RSS after all benchmarks | 7309 MB |
| Model load overhead | 7112 MB |
| Pipeline init time | 8.0 s |

A 4.07 GiB Q4_K_M model costs ~7 GB resident on CPU once the KV cache for
`N_CTX = 4096` is allocated. This is the reason `MmapGenerator` (the C++
`llm_backend` worker) exists: it moves that footprint into a separate process
and keeps the API server's own RSS small.

### 2.6 Model choice

Decode throughput measured with `llama-bench` (Q4_K_M, `tg128`) on the same
20-core CPU:

| Model | Size | Decode | Prefill |
|---|---|---|---|
| `mistral-7b-instruct-v0.2` (default) | 4.07 GiB | 8.03 tok/s | 73 tok/s |
| `qwen2.5-3b-instruct` | 1.95 GiB | 14.77 tok/s | 143 tok/s |
| `stablelm-zephyr-3b` | 1.59 GiB | 18.74 tok/s | 117 tok/s |

Switching models means setting `Config.GENERATION_MODEL`,
`GENERATION_MODEL_FILE`, **and** `Config.PROMPT_TEMPLATE` together — the C++
worker applies the template by hand, and a mismatch degrades answers silently.

> **Scope of these numbers.** Only the project-level suite
> (`bench_marking/project_bench_mark/`) measures the real system. The
> per-module files under `bench_marking/modules_benchmark/` are still
> `time.sleep()` placeholders that measure nothing — do not quote them, and see
> [`TODO.md`](./TODO.md) if you want to replace one with a real measurement.

---

## 3. Benchmark configuration

### Hardware and OS

| | |
|---|---|
| CPU | Intel Core Ultra 7 255HX, 20 cores |
| RAM | 16 GB |
| GPU | none used — CPU-only inference |
| OS | Fedora Linux (kernel 7.1.x, x86_64) |
| Python | 3.12.12 (CPython, conda env `rag_env`) |
| pytest / pytest-benchmark | 9.1.1 / 5.2.3 |

`Config.N_GPU_LAYERS` is `-1`, but the stock `llama-cpp-python` wheel is
CPU-only, so it is a no-op here; the timings above are CPU timings. Check yours
with `python -c "import llama_cpp; print(llama_cpp.llama_supports_gpu_offload())"`.

### Models

| Role | Model |
|---|---|
| Generation | `TheBloke/Mistral-7B-Instruct-v0.2-GGUF` → `mistral-7b-instruct-v0.2.Q4_K_M.gguf` (4.07 GiB, Q4_K_M) |
| Embedding | `sentence-transformers/all-MiniLM-L6-v2` |
| Reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` |

### `config.py` values in effect

| Setting | Value | |
|---|---|---|
| `ANN_TOP_K` | 10 | ANN candidates, doubled before reranking |
| `RERANK_TOP_K` | 5 | passages surviving the cross-encoder |
| `MIN_RELEVANCE_SCORE` | 0.25 | validator gate |
| `MAX_RETRIES` | 2 | validator retry budget |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 256 / 50 | ingestion chunking |
| `EMBEDDING_BATCH_SIZE` | 64 | |
| `N_CTX` | 4096 | context window |
| `N_BATCH` | 512 | prompt-evaluation batch |
| `N_THREADS` | 0 → 20 | 0 means `os.cpu_count()` |
| `N_GPU_LAYERS` | -1 | no GPU build present; effectively CPU |
| `MAX_NEW_TOKENS` | 256 | a cap, not a target |
| `GEN_TEMPERATURE` | 0.1 | |
| `MAX_CONTEXT_CHUNKS` | 5 | passages offered to the model |
| `CHUNK_CHAR_LIMIT` | 1000 | per-passage truncation |
| `CTX_SAFETY_MARGIN` | 192 | tokens withheld from the prompt budget |
| `L1` / `L2` / `L3` cache capacity | 32 / 128 / 1024 | three-tier topic cache |

Storage during the run: PostgreSQL for chunk metadata and users, one FAISS
HNSW index per user, the server-side adapters in `AdpaterModule/`.

### Corpus

A single user's live index, ingested from the Wikipedia scraper
(`backend/wikipedia_scraper/`) — medical articles, breast cancer among them.
Queries are generated from the opening words of real stored chunks, so they are
questions the corpus can actually answer.

### Reproducing

```bash
cd backend
pip install pytest-benchmark psutil scikit-learn

# End-to-end, real data — writes benchmark.md and test/project_testing/test_reports.md
python bench_marking/project_bench_mark/run_real_benchmark.py

# The rest of the benchmark suite
pytest bench_marking/ -v -s
```

The script needs a populated database: at least one user and their ingested
chunks. Ingest something first (see the backend setup guide) or it exits early.
Details in [`backend/bench_marking/HOW_TO.md`](./backend/bench_marking/HOW_TO.md).

---

## 4. Setup guidelines

Two components, each with its own guide. Start with the backend — the frontend
is useless without it.

| Component | Guide | Covers |
|---|---|---|
| **Backend** (FastAPI, RAG pipeline, C++ worker) | **[`backend/README.md`](./backend/README.md)** | Docker, conda, and native installs; model download; GPU builds; configuration; API reference; known gaps |
| **Frontend** (Electron desktop client) | **[`Frontend/README.md`](./Frontend/README.md)** | Install and run, process architecture, IPC and service layer, backend integration contract |

The fastest path, once Docker is installed:

```bash
git clone git@github.com:Ajaysvasan/multi_model_rag_for_searching.git
cd multi_model_rag_for_searching

cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste as JWT_SECRET_KEY

# The GGUF is not baked into the image (1.6-4.4 GB). Fetch it once:
python backend/download_model.py

docker compose up --build -d db backend
docker compose logs -f backend        # wait for the model to load
curl http://localhost:8000/docs
```

Then run the desktop client:

```bash
cd Frontend && npm install && npm start
```

Other documents worth knowing about:

- [`backend/SETUP.md`](./backend/SETUP.md) — longer backend walkthrough
- [`FILE_OPENING_FLOW.md`](./FILE_OPENING_FLOW.md) — how a source chip in the UI resolves to a file on disk
- [`backend/test/HOW_TO.md`](./backend/test/HOW_TO.md) — running the test suites
- [`backend/bench_marking/HOW_TO.md`](./backend/bench_marking/HOW_TO.md) — running the benchmarks
- Each backend layer carries its own `<layer>.md` (design) and `<layer>_API_DOCS.md` (reference); the index is in [`backend/README.md`](./backend/README.md#3-layer-reference)

---

## 5. Contributing

Fork, branch off `main`, open a pull request. Beyond that, three things are
expected of every contribution.

### 5.1 Write tests for the code you write

A change without a test does not get merged. Tests live beside the structure
they cover:

```
backend/test/module_testing/<layer>/test_<layer>.py    unit tests for one layer
backend/test/project_testing/test_project.py           end-to-end and stress tests
backend/llm_backend/tests/                             C++ suites (GoogleTest + ctest)
backend/bench_marking/modules_benchmark/<layer>/       per-layer benchmarks
backend/bench_marking/project_bench_mark/              whole-pipeline benchmarks
```

Run them before you push:

```bash
cd backend
pytest test/ -v                                        # Python suites
pytest bench_marking/ -v -s                            # benchmarks
ctest --test-dir llm_backend/build --output-on-failure # C++ suites
```

Rules of thumb:

- **New layer or module → new test directory**, mirroring the layout above, plus
  the two documents every layer carries: `<layer>.md` explaining why it exists,
  and `<layer>_API_DOCS.md` with runnable examples.
- **Bug fix → a test that fails before the fix and passes after it.** Name it
  after the behaviour, not the bug number.
- **Don't fake a measurement.** A benchmark that calls `time.sleep()` to stand
  in for real work is worse than no benchmark, because it ends up quoted. If you
  cannot measure the real thing yet, leave the file out and add a `TODO.md` entry.
- Tests that need a model must skip, not fail, when no `.gguf` is present — the
  C++ engine suite already does this, and a fresh checkout has to stay green.
- Update the generated reports (`reports.md`, `bench_mark.md`) when your change
  moves the numbers.

### 5.2 Raising an issue

Open issues at
[github.com/Ajaysvasan/multi_model_rag_for_searching/issues](https://github.com/Ajaysvasan/multi_model_rag_for_searching/issues).
Before you do, check the **Known gaps** section of
[`backend/README.md`](./backend/README.md#8-known-gaps) and [`TODO.md`](./TODO.md)
— several rough edges are already recorded there, and an issue that duplicates
one of them is better filed as a comment on the corresponding TODO item.

A useful issue includes:

1. **What you ran** — the exact command, endpoint, or UI action.
2. **What happened vs. what you expected**, with the error text or the wrong
   answer pasted in full.
3. **Environment** — OS, Python version, install route (Docker / conda /
   native), and whether the C++ worker is in use.
4. **Configuration that differs from the defaults** — model, `N_CTX`,
   `ANN_TOP_K`, GPU or CPU. Most retrieval-quality reports come down to this.
5. **Logs** — `docker compose logs backend`, or the backend's stdout.
6. **A minimal reproduction** where possible: the smallest document and query
   that show the problem.

Tag it as `bug`, `enhancement`, `docs`, `backend`, `frontend`, or
`performance`. Security-relevant findings — auth, token handling, the fact that
`/upload` accepts arbitrary host paths — go to the maintainer privately rather
than into a public issue.

### 5.3 Use `TODO.md` for upcoming work

[`TODO.md`](./TODO.md) is the single list of what is planned, in progress, and
recently done, split into critical and minor work for both components. It
replaces the old `backend/todo.txt`.

The workflow:

- **Before starting**, claim the item — comment on the linked issue, or open one
  that references the TODO line — so two people don't build the same thing.
- **If your work isn't on the list**, add it there in the same pull request. New
  entries go under the right heading as an unchecked box, one line, phrased as
  the outcome rather than the activity.
- **When you finish**, tick the box in the same PR that lands the code and move
  it to *Recently done* with the PR number. A TODO item and its implementation
  land together.
- **When you discover work you are not going to do now** — a stub, a known bad
  path, a missing test — write it into `TODO.md` instead of leaving it in a code
  comment where nobody reads it.

Keep the list short enough to be read in one sitting. If an item has grown into
a project, it belongs in an issue, with `TODO.md` holding just the one-line
pointer.
