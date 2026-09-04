# TUI_services — terminal command layer

[← Back to BACKEND.md](../BACKEND.md) · [API reference](TUI_services_API_DOCS.md)

The command implementations behind `agent.py`: `start`, `ingest`, `blame`,
`clear`.

## The problem

The FastAPI server needs PostgreSQL, an Electron client, and JWT configuration
before it answers a single question. That is a lot of moving parts when you only
want to point the thing at a folder and ask it something — during development,
when debugging retrieval, or as a genuinely offline single-user tool.

The TUI is that path: no database server, no browser, no auth.

## Design

Each command is one module with one entry point, dispatched by a `match` in
`agent.py`. The layer holds no state and owns no resources — it composes what
`system_services/tui` builds.

| Command | Module | Does |
|---|---|---|
| `start` | `start.py` | Initialise, then loop reading questions |
| `ingest` | `ingest_command.py` | Index a path, or scan broadly by default |
| `blame` | `blame.py` | Print the last recorded timings |
| `clear` | `clear.py` | Delete local index and database files |

### `blame` and the timing log

`logger.write_logs(type, start, end)` records durations to
`logs/tui_perf.json`, and `blame` prints them. The name follows `git blame`:
"what took the time?"

Startup dominates a TUI session — the embedding model, the cross-encoder and a
multi-gigabyte GGUF all load before the first question — so distinguishing
"initialisation was slow" from "that query was slow" is the difference between
tuning the right thing and the wrong one.

### `clear`

Deletes the FAISS index, its `.ids` sidecar, the chunk metadata database, and
the cache/history database, reading every path from `Config` rather than
hardcoding. Re-ingestion from scratch is the recovery path for a corrupted index
or a changed `NORMALIZATION_VERSION`.

## Known issues

- **`start.py` can raise `NameError`.** `extracted_text` is assigned only inside
  the branch for text extensions, but the `print` that uses it sits outside. An
  image or audio citation — both supported modalities — hits an unbound name, or
  silently prints the previous file's text.
- **The default `ingest` scans far too widely.** With no `--path` it starts at
  `/home` on Linux and walks everything.
- **`logger.write_logs` opens with `"w"`.** Each write truncates, so despite the
  docstring saying "line by line", only the most recent entry survives — and
  since `start()` writes `init` and then `last_query`, the init timing is gone
  before you can ask for it. `"a"` would make it a real JSONL trace.
- **`ingest_command.py` uses a bare `except:`** around its import, re-raising a
  generic exception that discards the original traceback.
