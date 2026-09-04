# cache_layer — API reference

[← Back to BACKEND.md](../BACKEND.md) · [Design notes](cache_layer.md)

## `TopicKey` / `TopicState`

```python
from cache_layer.TopicState import TopicKey, TopicState

key = TopicKey(
    topic_label="breast cancer screening",
    modality_filter="text",          # "text" | "image" | "audio" | "any"
    retrieval_policy="default",
)
```

`TopicKey` is frozen and hashable — use it directly as a dict key.
`TopicState` carries `key`, `cached_chunk_ids`, `access_count`,
`last_access_ts`, `first_seen_ts`, `score`, `confidence`.

## `TopicCacheManager`

```python
from cache_layer.cache import TopicCacheManager
from retrieval_layer.retrieval_engine import QueryRouter

cache = TopicCacheManager()      # loads from Config.METADATA_DB_PATH

key = QueryRouter.build_topic_key("breast cancer screening")

state = cache.lookup(key)
if state is None:
    chunk_ids = run_expensive_retrieval()
    cache.insert_new(key, cached_chunk_ids=chunk_ids)
else:
    chunk_ids = state.cached_chunk_ids   # access counted, maybe promoted
```

| Method | Returns | Notes |
|---|---|---|
| `lookup(key)` | `TopicState \| None` | Counts the access, may promote, persists |
| `insert_new(key, cached_chunk_ids)` | `TopicState` | Enters at L3. Existing key returns the current state **without updating the IDs** |
| `debug_counts()` | `dict` | `{"L1": n, "L2": n, "L3": n, "TOTAL": n}`; asserts invariants |
| `debug_dump_levels()` | `dict` | Keys per tier; asserts invariants |

> `insert_new` on an existing key is a no-op for the stored IDs. To refresh a
> topic's chunk set after re-ingestion, delete the entry first.

## Worked example

```python
from cache_layer.cache import TopicCacheManager
from cache_layer.TopicState import TopicKey

cache = TopicCacheManager()
key = TopicKey("mitosis", "text", "default")

cache.insert_new(key, ["chunk_a", "chunk_b"])
print(cache.debug_counts())        # {'L1': 0, 'L2': 0, 'L3': 1, 'TOTAL': 1}

for _ in range(3):                 # L3_THRESHOLD = 3
    cache.lookup(key)
print(cache.debug_counts())        # promoted to L2

for _ in range(8):                 # L2_THRESHOLD = 8
    cache.lookup(key)
print(cache.debug_counts())        # promoted to L1
```

## Substituting your own cache

`RetrievalEngine` needs only two methods, so any object of this shape works:

```python
class NullCache:
    def lookup(self, key):
        return None
    def insert_new(self, key, cached_chunk_ids=None):
        pass

engine = RetrievalEngine(cache=NullCache(), ...)
```

This is exactly what `AdpaterModule._UserCacheAdapter` does for the server path.

## Configuration

| `Config` key | Default | Meaning |
|---|---|---|
| `L1_CAPACITY` | 32 | Hot tier size |
| `L2_CAPACITY` | 128 | Warm tier size |
| `L3_CAPACITY` | 1024 | Cold tier size; overflow evicts |
| `L3_THRESHOLD` | 3 | Accesses to promote L3 → L2 |
| `L2_THRESHOLD` | 8 | Accesses to promote L2 → L1 |
| `METADATA_DB_PATH` | `data/index/chunks.db` | SQLite file holding `cache_entries` |

## Persistence

The `cache_entries` table is created on construction if absent. All state is
reloaded at startup, ordered by level then recency. Clearing the cache means
deleting the rows:

```python
import sqlite3
from config import Config

conn = sqlite3.connect(Config.METADATA_DB_PATH)
conn.execute("DELETE FROM cache_entries")
conn.commit()
conn.close()
```
