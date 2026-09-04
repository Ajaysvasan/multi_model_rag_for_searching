# history_layer — API reference

[← Back to BACKEND.md](../BACKEND.md) · [Design notes](history_layer.md)

## `ConversationHistory`

```python
from history_layer.history import ConversationHistory
from config import Config

history = ConversationHistory(
    max_size=32,
    sim_threshold=0.80,        # cosine; the TUI uses 0.90
    session_id="sess-1",
    db_path=str(Config.CACHE_HISTORY_DB_PATH),
    max_age_seconds=3600,
)
```

Loads that session's entries from SQLite on construction.

| Method | Returns | Notes |
|---|---|---|
| `find_similar(query_embedding)` | `list[str] \| None` | Chunk IDs of the newest entry above threshold; evicts stale first |
| `add_or_update(topic_key, query_embedding, chunk_ids)` | `None` | Replaces any entry with the same `TopicKey`, moving it to newest |
| `clear()` / `clear_session()` | `None` | Empties memory and this session's rows |
| `size()` | `int` | Entries currently held |

## Worked example

```python
import numpy as np
from history_layer.history import ConversationHistory
from retrieval_layer.retrieval_engine import QueryRouter

history = ConversationHistory(session_id="sess-1", sim_threshold=0.85)

q1 = "breast cancer screening guidelines"
vec1 = embed_model.encode(q1, normalize_embeddings=True)
history.add_or_update(QueryRouter.build_topic_key(q1), vec1, ["c1", "c2", "c3"])

q2 = "guidelines for screening breast cancer"
vec2 = embed_model.encode(q2, normalize_embeddings=True)

reused = history.find_similar(vec2)
if reused is not None:
    print("history hit:", reused)      # ['c1', 'c2', 'c3']
else:
    reused = run_ann_search(vec2)
    history.add_or_update(QueryRouter.build_topic_key(q2), vec2, reused)
```

## `HistoryEntry`

```python
from history_layer.history_node import HistoryEntry
```

Fields: `topic_key` (`TopicKey`), `query_embedding` (`np.ndarray`, normalised),
`chunk_ids` (`list[str]`), `timestamp` (`float`, epoch seconds).

## Notes on behaviour

- Vectors are normalised on insert, so `find_similar` uses a dot product.
  Passing an unnormalised vector still works — it is normalised on the way in.
- `find_similar` returns the **newest** qualifying entry, not the closest.
- Both `find_similar` and `add_or_update` evict stale entries first, so ageing
  needs no background task.
- Embeddings persist as raw `float32` bytes; changing the embedding model
  invalidates stored vectors. Clear the table when you switch models.

## Server-side equivalent

```python
from system_services.server.pg_history import PgConversationHistory

history = PgConversationHistory(sim_threshold=0.90, max_age_seconds=3600)
history.add_or_update(user_id, "topic label", vec, ["c1", "c2"])
ids = history.find_similar(user_id, vec)      # list[str] | None
```

Same semantics, per-user, **in memory only** — nothing is persisted, so entries
do not survive a restart.

## Configuration

| `Config` key | Default | Meaning |
|---|---|---|
| `HISTORY_MAX_SIZE` | 32 | Entries retained per session |
| `HISTORY_MAX_AGE` | 3600 | Seconds before an entry goes stale |
| `CACHE_HISTORY_DB_PATH` | `data/index/cache_history.db` | SQLite file |
| `DB_PATH` | same | Default `db_path` argument |
