# system_services — API reference

[← Back to BACKEND.md](../BACKEND.md) · [Design notes](system_services.md)

## Server

### `load_shared_components()`

```python
from system_services.server.system_init import load_shared_components

shared = load_shared_components()      # slow: loads embedding model + LLM
```

Returns:

| Key | Type | Notes |
|---|---|---|
| `embed_model` | `SentenceTransformer` | |
| `dim` | `int` | Embedding dimension |
| `generator` | `LlamaGenerator` | Loaded and ready |
| `faiss_manager` | `UserFaissManager` | |
| `pg_cache` | `PgTopicCache` | |
| `pg_history` | `PgConversationHistory` | In-memory |
| `pg_conv_memory` | `PgConversationMemory` | |

Call once per process. In FastAPI, from the lifespan hook:

```python
from contextlib import asynccontextmanager
import asyncio

state = {"shared": None, "ready": False}

@asynccontextmanager
async def lifespan(app):
    loop = asyncio.get_event_loop()
    # Blocking: run it off the event loop.
    state["shared"] = await loop.run_in_executor(None, load_shared_components)
    state["ready"] = True
    yield

app = FastAPI(lifespan=lifespan)
```

### `UserFaissManager`

```python
from system_services.server.user_faiss_manager import UserFaissManager

manager = UserFaissManager(dim=384)
index = manager.get_index(user_id)       # creates data/users/<uuid>/ on demand
ids = index.search(query_vector, k=10)
```

Indexes are cached in-process. Serialise writes yourself — see the race noted in
the design document.

### `ingestion_pipeline`

```python
from system_services.server.ingestion_orchestrator import ingestion_pipeline

result = ingestion_pipeline(user_id, "/path/to/file-or-directory", shared)
# {"status": "success", "processed_files": 3, "chunks_added": 47}
```

Returns `{"error": "Path not found"}` for a missing path and
`{"status": "skipped", "reason": "unsupported_extension"}` for an unknown type.
Handles `.pdf .txt .doc .docx .jpg .jpeg .png .mp3 .wav .m4a .flac .ogg`.

Already-ingested chunks are skipped, so re-running over a folder is cheap.

### PostgreSQL stores

```python
from system_services.server.pg_chunk_store import PgChunkStore

store = PgChunkStore()
doc_id = store.add_document_if_not_exists(user_id, "/docs/a.pdf", "a.pdf", "text")
rows   = store.get_by_ids(["c1", "c2"], user_id)          # order preserved
paths  = store.get_source_paths(["c1"], user_id)          # {chunk_id: path}
store.insert_chunks(chunk_rows)
store.insert_embeddings(embedding_rows)
```

```python
from system_services.server.pg_conversation_memory import PgConversationMemory

mem = PgConversationMemory(max_turns=10)
mem.add_turn(user_id, session_id, "user", "What causes it?")
mem.get_context(user_id, session_id, max_turns=4)
mem.get_recent_queries(user_id, session_id, max_queries=3)
```

`session_id` must be a real `history_sessions` UUID, not the user's ID.

## TUI

### `initialize_system()`

```python
from system_services.tui.system_init import initialize_system

engine, metadata_store, conv_memory, session_id, query_preprocessor = \
    initialize_system()                       # or initialize_system(ingestion_config=cfg)
```

Loads the embedding model, optionally ingests, opens the FAISS index and SQLite
metadata store, builds cache/history/memory, loads the LLM, and returns a wired
`RetrievalEngine`.

### `run_query_loop()`

```python
from system_services.tui.query_loop import run_query_loop

run_query_loop(engine, conv_memory, session_id, query_preprocessor)
```

Commands: `/retrieve <query>` for chunks only, `/new` for a fresh session,
`quit`/`exit`/`q` to leave.

### Ingestion

```python
from system_services.tui.ingestion_pipeline import run_ingestion, check_ingestion_exists
from system_services.tui.ingestion_menu import collect_ingestion_config

if not check_ingestion_exists():
    config = collect_ingestion_config()        # interactive
    run_ingestion(model, dim, config)
```

`collect_ingestion_config(raw="1,2")` skips the prompt. The config shape is
`{"text": path|None, "image": path|None, "audio": path|None}`.

## Complete server example

```python
from uuid import UUID
from AdpaterModule.CacheAdapter import _UserCacheAdapter
from AdpaterModule.HistoryAdapter import _UserHistoryAdapter
from AdpaterModule.MetaDataAdapter import _UserMetadataAdapter
from AdpaterModule.ConvMemoryAdapter import _UserConvMemoryAdapter
from retrieval_layer.retrieval_engine import QueryProcessing, RetrievalEngine
from system_services.server.pg_chunk_store import PgChunkStore
from config import Config

def answer(user_id: UUID, session_id: str, question: str, shared: dict):
    conv = _UserConvMemoryAdapter(shared["pg_conv_memory"], user_id)
    engine = RetrievalEngine(
        cache=_UserCacheAdapter(shared["pg_cache"], user_id),
        index=shared["faiss_manager"].get_index(user_id),
        embedding_model=shared["embed_model"],
        history=_UserHistoryAdapter(shared["pg_history"], user_id),
        ann_top_k=Config.ANN_TOP_K,
        metadata_store=_UserMetadataAdapter(PgChunkStore(), user_id),
        generator=shared["generator"],
        conversation_memory=conv,
    )
    pre = QueryProcessing(conv, embedding_model=shared["embed_model"])

    conv.add_turn(session_id, "user", question)
    response = engine.retrieve_and_generate(
        question, pre.preprocess_query(question, session_id), session_id=session_id
    )
    conv.add_turn(session_id, "assistant", response.answer)
    return response
```
