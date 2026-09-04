# AdpaterModule — PostgreSQL ↔ engine adapters

[← Back to BACKEND.md](../BACKEND.md) · [API reference](AdpaterModule_API_DOCS.md)

Four thin classes that let the shared retrieval engine run against PostgreSQL
without knowing PostgreSQL exists.

*(The directory name is misspelled — "Adpater" — and left alone because every
import in the project references it.)*

## The problem

`RetrievalEngine` was written against the single-user TUI stores:
`TopicCacheManager`, `ConversationHistory`, `ChunkMetadataStore`. Their methods
take no user argument, because in the TUI there is only one user.

The server has many users and PostgreSQL-backed stores whose methods all need a
`user_id`. Two obvious options, both bad:

1. **Thread `user_id` through the engine.** Pollutes every signature with a
   concept the TUI does not have.
2. **Fork the engine.** Two copies of the retrieval logic to keep in sync.

## Design

The adapter pattern, closing over `user_id`:

```
  RetrievalEngine ──▶ cache.lookup(key)
                          │
                          ▼
              _UserCacheAdapter(pg_cache, user_id)
                          │
                          ▼
                 pg_cache.lookup(user_id, key.topic_label)
```

Each adapter is constructed per request with the authenticated user's ID and
presents exactly the interface the engine expects. The engine stays
single-tenant in its own terms; multi-tenancy lives entirely at this boundary.

| Adapter | Wraps | Presents |
|---|---|---|
| `_UserCacheAdapter` | `PgTopicCache` | `lookup`, `insert_new` |
| `_UserHistoryAdapter` | `PgConversationHistory` | `find_similar`, `add_or_update` |
| `_UserMetadataAdapter` | `PgChunkStore` | `get_by_ids`, `count_chunks`, `has_chunk` |
| `_UserConvMemoryAdapter` | `PgConversationMemory` | `add_turn`, `get_context`, `get_recent_queries`, `close` |

They are cheap objects holding two references, so constructing four per request
costs nothing. The underlying stores are shared and created once at startup.

## Current state — two of the four are stubs

This is the layer's most important property to know about.

**`_UserCacheAdapter.lookup` always returns `None`.** It calls through (which
still bumps the access counter) and then discards the result, because
`cache_topics` has no column to store chunk IDs in. The server therefore takes
the ANN path on every query and pays for a cache that cannot hit — the write
cost with none of the benefit.

**`_UserHistoryAdapter`** delegates to `PgConversationHistory`, which keeps
entries in a per-process dictionary rather than the database. History works
within one process and vanishes on restart, and is not shared across workers.

**`_UserMetadataAdapter.count_chunks` returns a hardcoded `0`.** Nothing in the
retrieval path uses it, but it will mislead anything that does.

The interfaces are right; the persistence is unfinished. Completing it means
adding a `chunk_ids JSONB` column to `cache_topics` and an embedding column to
the history tables, then replacing the stub bodies — no engine changes.

## Why this shape is still worth having

Even with the stubs, the boundary is doing its job: the server swapped its
entire storage backend without the retrieval layer changing, and finishing the
persistence is a change confined to these four files and two migrations.
