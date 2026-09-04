# system_services — composition and startup

[← Back to BACKEND.md](../BACKEND.md) · [API reference](system_services_API_DOCS.md)

Where the layers are assembled into a working system. Two subpackages, one per
front end.

## The problem

Every other layer is a component with no opinion about how it is wired. Someone
has to decide which storage backend is used, load the models exactly once,
sequence startup, and hand the pieces to `RetrievalEngine`. Doing that inside
the layers would couple them to each other; doing it inside `main.py` would
duplicate it for the TUI.

There is also a hard startup constraint: the embedding model, the reranker and
the LLM together take tens of seconds and gigabytes. They must be loaded once
per process and shared, never per request.

## Design

```
  system_services/
    server/   FastAPI: PostgreSQL, per-user FAISS, adapters
    tui/      terminal: SQLite, single index, direct stores
```

Both build the same `RetrievalEngine` from different parts. The engine's
constructor is the seam.

### Server composition

`load_shared_components()` runs once, inside the FastAPI lifespan hook, and
returns a dict of process-wide singletons: the embedding model, its dimension,
the generator, the FAISS manager, and the three PostgreSQL stores. The web layer
holds it in module state and builds only cheap per-request objects (four
adapters) on top.

`UserFaissManager` keeps one `HNSWIndex` per user under
`data/users/<uuid>/`, created on demand and cached in a dict. Physical
separation of indexes means a retrieval can only ever return the requesting
user's vectors — isolation by construction rather than by a `WHERE` clause.

`ingestion_orchestrator` runs the write path: resolve files by type, transcribe
audio, OCR images, extract and normalise text, chunk, embed, then write to FAISS
and PostgreSQL together. It checks both stores before embedding, so re-ingesting
a folder is cheap.

### TUI composition

`initialize_system()` is the same assembly against local stores, plus an
interactive first-run ingestion prompt when no index exists. It prints a
numbered startup sequence because model loading is slow enough that silence
looks like a hang.

## Known issues

- **`UserFaissManager.get_index` has a check-then-act race.** It checks the dict
  under a lock, releases it, builds and loads the index, then re-acquires. Two
  concurrent first requests for the same user build two indexes and one wins.
  `HNSWIndex.add`/`save` are unlocked too, so concurrent ingestion for one user
  can tear the index and its `.ids` sidecar apart — and `load()` asserts they
  match, so the next start fails.
- **The TUI generator selection is dead code.** The Linux/macOS branch assigns
  `MmapGenerator` to a misspelled local (`geneator`), and the next statement
  overwrites `generator` with `LlamaGenerator` unconditionally. The C++ backend
  is never selected on any path.
- **The server never offers `MmapGenerator`.** `load_shared_components`
  constructs `LlamaGenerator` directly.
- **Startup is serial.** The embedding model and the LLM load one after the
  other; they are independent and could overlap.
