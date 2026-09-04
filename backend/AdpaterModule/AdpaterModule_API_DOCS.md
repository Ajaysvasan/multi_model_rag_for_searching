# AdpaterModule — API reference

[← Back to BACKEND.md](../BACKEND.md) · [Design notes](AdpaterModule.md)

## Wiring a per-request engine

```python
from uuid import UUID

from AdpaterModule.CacheAdapter import _UserCacheAdapter
from AdpaterModule.HistoryAdapter import _UserHistoryAdapter
from AdpaterModule.MetaDataAdapter import _UserMetadataAdapter
from AdpaterModule.ConvMemoryAdapter import _UserConvMemoryAdapter
from retrieval_layer.retrieval_engine import RetrievalEngine
from system_services.server.pg_chunk_store import PgChunkStore
from config import Config

user_id = UUID(user_id_str)
shared = app_state["shared"]          # built once at startup

engine = RetrievalEngine(
    cache=_UserCacheAdapter(shared["pg_cache"], user_id),
    index=shared["faiss_manager"].get_index(user_id),
    embedding_model=shared["embed_model"],
    history=_UserHistoryAdapter(shared["pg_history"], user_id),
    ann_top_k=Config.ANN_TOP_K,
    history_enabled=True,
    metadata_store=_UserMetadataAdapter(PgChunkStore(), user_id),
    generator=shared["generator"],
    conversation_memory=_UserConvMemoryAdapter(shared["pg_conv_memory"], user_id),
)
```

Adapters are per-request and disposable; the stores they wrap are shared.

## `_UserCacheAdapter`

```python
adapter = _UserCacheAdapter(pg_cache, user_id)
adapter.lookup(topic_key)                  # -> always None (see below)
adapter.insert_new(topic_key, chunk_ids)   # chunk_ids is accepted and ignored
```

| Method | Behaviour |
|---|---|
| `lookup(key)` | Calls `PgTopicCache.lookup`, then returns `None` unconditionally |
| `insert_new(key, cached_chunk_ids=None)` | Records the topic and bumps its score; **does not store the chunk IDs** |

> `cache_topics` has no chunk-IDs column, so a hit cannot be served. Every query
> falls through to ANN search. Restoring caching means adding the column and
> returning a real `TopicState` here.

## `_UserHistoryAdapter`

```python
adapter = _UserHistoryAdapter(pg_history, user_id)

ids = adapter.find_similar(query_embedding)       # list[str] | None
adapter.add_or_update(topic_key, query_embedding, chunk_ids)
```

Functional, but backed by a per-process dict — not persisted, not shared between
workers, lost on restart.

## `_UserMetadataAdapter`

```python
adapter = _UserMetadataAdapter(PgChunkStore(), user_id)

rows = adapter.get_by_ids(["c1", "c2"])   # list[dict], input order preserved
adapter.has_chunk("c1")                    # bool
adapter.count_chunks()                     # always 0 -- not implemented
```

Rows carry `chunk_id`, `document_id`, `chunk_index`, `start_offset`,
`end_offset`, `chunk_text`, plus `source_path` and `modality` as empty strings
(`PgChunkStore.get_by_ids` does not join `documents`). Resolve real paths
separately:

```python
paths = PgChunkStore().get_source_paths(chunk_ids, user_id)   # {chunk_id: path}
```

## `_UserConvMemoryAdapter`

```python
adapter = _UserConvMemoryAdapter(pg_conv_memory, user_id)

adapter.add_turn(session_id, "user", "What are the risk factors?")
adapter.add_turn(session_id, "assistant", answer_text)

adapter.get_context(session_id, max_turns=4)
# [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

adapter.get_recent_queries(session_id, max_queries=3)   # list[str], user turns only
adapter.close()                                          # no-op; the pool is shared
```

> **`session_id` must be a `history_sessions` primary key.** `main.py` currently
> passes `str(user_id)`, which never matches, so every `add_turn` creates a new
> session row and `get_context` always returns `[]`. Allocate one session per
> conversation and pass its ID.

## Writing a new adapter

Implement only what the engine calls:

```python
class _UserCacheAdapter:
    def __init__(self, backend, user_id):
        self._backend, self._uid = backend, user_id

    def lookup(self, key):
        state = self._backend.lookup(self._uid, key.topic_label)
        return state                      # TopicState | None

    def insert_new(self, key, cached_chunk_ids=None):
        self._backend.insert_new(self._uid, key.topic_label, cached_chunk_ids)
```

The full set of interfaces the engine depends on is tabulated in the
[retrieval layer API docs](../retrieval_layer/retrieval_layer_API_DOCS.md).
