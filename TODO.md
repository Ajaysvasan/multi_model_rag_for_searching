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
      for chunk IDs, so `_UserCacheAdapter.lookup()` always returns `None` and
      the server takes the ANN path on every query; history is per-process and
      lost on restart. See [`AdpaterModule.md`](./backend/AdpaterModule/AdpaterModule.md).
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

- [x] **Project benchmarking.** Real-data suite in
      `bench_marking/project_bench_mark/run_real_benchmark.py`; results in
      [`benchmark.md`](./backend/bench_marking/project_bench_mark/benchmark.md)
      and summarised in the [README](./README.md#2-benchmarks). Module-level
      benchmarks are still stubs — see above.
