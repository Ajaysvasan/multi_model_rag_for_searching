# TODO

The single list of what is planned, in progress, and recently finished. See the
[contributing section of the README](./README.md#53-use-todomd-for-upcoming-work)
for how to use this file: claim an item before starting it, add anything you
work on that isn't listed, and tick the box in the same pull request that lands
the code.

Replaces the old `backend/todo.txt`.

---

## Backend — critical

- [ ] **Model cleanup / teardown.** No clean shutdown path for the loaded model;
      add one so the process releases weights and the KV cache deterministically.
- [ ] **Answer quality.** The model still does not respond as intended on some
      queries — track down whether it is the prompt, the context budget, or the
      retrieved passages.
- [ ] **Finish the C++ layer.** Extend `llm_backend/` and fix the outstanding
      bugs in it; it is the path that keeps the API server's RSS low.
- [ ] **Run inference through C++ by default.** `MmapGenerator` works but is not
      the default; make the switch once the worker is trusted.
- [ ] **Move to a smaller model.** Mistral-7B costs ~7 GB resident and 8 tok/s
      decode on CPU. Qwen2.5-3B and StableLM-Zephyr-3B are 2-2.3x faster at a
      third of the size — evaluate answer quality before switching
      (`Config.PROMPT_TEMPLATE` must change with the model).
- [ ] **Server-side cache and history are stubs.** `cache_topics` has no column
      for chunk IDs, so `_UserCacheAdapter.lookup()` always returns `None`;
      history is per-process and lost on restart. Now measured rather than
      suspected: **0 hits in 25 lookups in every ablation configuration**, so
      the cache-on and cache-off rows are the same pipeline. See
      [`AdpaterModule.md`](./backend/AdpaterModule/AdpaterModule.md).

- [ ] **The cross-encoder is skipped on every warm query.**
      `retrieve_enhanced` gates it on `source == "ann"`, so as soon as history
      serves a query the expensive reranker is bypassed and the lightweight
      embedding rerank runs instead. Measured: `ann=0/24` on all cache/history
      rows. Decide whether that is the intent — if it is, say so in
      `reranking.md`; if not, rerank on the history path too.
- [ ] **`/query` passes the user ID as the session ID.** It never matches a
      `history_sessions` row, so a new session is created per turn: multi-turn
      context is lost and the table grows unboundedly.
- [ ] **Generation is single-threaded and unlocked.** One `Llama` instance is
      shared across a thread pool with no lock; concurrent requests are unsafe.
- [ ] **`/speech-query` does not exist.** The Electron client calls it; only the
      ingestion half of the audio pipeline is wired up.
- [ ] **`/upload` accepts arbitrary host paths.** Fine for a single-user desktop
      install, not for anything shared.

## Backend — minor

- [ ] **Clean up `main.py`.** It has grown messy; split the route handlers from
      the composition logic.
- [ ] **Mode feature.** Not started.
- [ ] **Logger.** Implement a real logging function instead of scattered prints.
- [ ] **Replace the placeholder benchmarks.** Every file under
      `bench_marking/modules_benchmark/` is a `time.sleep()` stub that measures
      nothing. Replace them layer by layer with real measurements, or delete
      them — as written they produce numbers people will quote.
- [ ] **Unit tests for the untested layers.** `test/module_testing/` covers only
      `data_layer`, `generation_layer`, and `retrieval_layer`. Cache, history,
      reranking, validation, security, and the adapters have none.

- [ ] **Harder benchmark queries.** Known-item Recall@5 is 1.00 in every
      configuration, so the query set can detect gross breakage but cannot rank
      configurations against each other. Hand-written questions with judged
      relevant chunks would make the ablation discriminative.
- [ ] **New feature or layer.** Open-ended; propose in an issue first.
- [ ] **Java for the system plumbing** — job scheduling, thread pools, event
      driven task management. Someday, not now.

## Frontend

- [ ] **Fix the stale document links in `Frontend/README.md`.** It points at
      `BACKEND_DEVELOPER_START_HERE.md`, `BACKEND_INTEGRATION_GUIDE.md`, and
      `backend/FRONTEND_RESPONSE_FORMAT.md`, none of which exist any more — the
      content now lives in [`backend/README.md`](./backend/README.md).
- [ ] **Point `ragService.js` at the real backend.** Parts of it still simulate
      the RAG pipeline instead of calling the API.
- [ ] **Speech query end to end.** Blocked on the backend `/speech-query`
      endpoint above.
- [ ] Design polish and bug fixes are always welcome — no issue needed for small
      ones.

---

## Recently done

- [x] **Fixed the ablation harness.** It disabled a stage by assigning `None` to
      `engine._reranker` — the not-built-yet sentinel the property rebuilds
      from — so every configuration ran the full pipeline, and the headline
      "134x slower" was a cross-encoder model load inside a timed region. Gold
      labels were also taken from the pipeline's own output, pinning NDCG at
      1.00 by construction. The engine now has real `reranker_enabled` /
      `validator_enabled` / `lightweight_rerank_enabled` flags, relevance
      labels are known-item, each row is verified by counting proxies, and
      `test/module_testing/retrieval_layer/test_ablation_flags.py` fails if the
      sentinel trick comes back.

- [x] **Project benchmarking.** Real-data suite in
      `bench_marking/project_bench_mark/run_real_benchmark.py`; results in
      [`benchmark.md`](./backend/bench_marking/project_bench_mark/benchmark.md)
      and summarised in the [README](./README.md#2-benchmarks). Module-level
      benchmarks are still stubs — see above.
