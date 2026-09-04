# cache_layer — three-tier topic cache

[← Back to BACKEND.md](../BACKEND.md) · [API reference](cache_layer_API_DOCS.md)

Remembers which chunks answered which topic, so a repeated question skips
embedding and vector search entirely.

## The problem

Retrieval is the cheap half of a RAG query, but it is not free: embedding costs
~2 ms, the ANN search ~0.1 ms, reranking ~19 ms, validation ~18 ms. In a chat
session users repeat and rephrase constantly. Recomputing an identical result
set is pure waste.

A flat LRU is the obvious answer and the wrong one. It cannot distinguish "asked
once, three weeks ago" from "asked forty times today" — both are just entries,
and a burst of one-off questions evicts the genuinely hot ones.

## Design

Three tiers, promotion by access count, demotion by LRU, modelled on a CPU cache
hierarchy:

```
        promote at ≥8 accesses          promote at ≥3 accesses
   L1 ◀──────────────────────── L2 ◀──────────────────────── L3 ◀── new entries
   32                          128                          1024
   entries                     entries                      entries
        ────────────────────▶       ────────────────────▶        ──▶ evicted
        demote (LRU) on overflow    demote (LRU) on overflow
```

New topics always enter at L3. Surviving repeated access earns promotion.
Overflow at any tier demotes the least-recently-used entry down rather than
discarding it, so a once-hot topic degrades gracefully instead of vanishing.
Only overflow at L3 evicts.

The effect is that frequency and recency are tracked separately: L1 holds the
genuinely hot working set, and a burst of novel questions churns L3 without
disturbing it.

### Keys

`TopicKey` is a frozen dataclass of `(topic_label, modality_filter,
retrieval_policy)` — hashable, so it is a dict key directly. `topic_label` is
the normalised query text; `modality_filter` comes from `QueryRouter`, so "show
me the screenshot about X" and "find the document about X" are different cache
entries even though the topic matches.

### Persistence

Every mutation writes through to SQLite immediately (`CacheLoader`), and the
whole cache is reloaded into the three `OrderedDict`s at construction. The cache
survives restarts, which matters for a desktop tool that is opened and closed
constantly.

The write-through is synchronous and unbatched — a deliberate simplicity
trade-off. At the access rates a single-user desktop tool sees, the SQLite write
is invisible next to generation.

### Invariants

`_assert_invariants` checks that the union of the three tiers exactly equals the
directory. `debug_counts()` and `debug_dump_levels()` run it, so tests get the
check for free.

## Trade-offs and limits

- **No TTL.** Entries live until evicted by pressure. A topic whose underlying
  documents change keeps its stale chunk IDs. Re-ingestion should clear the
  cache; nothing enforces that.
- **Exact-match keys.** "breast cancer screening" and "screening for breast
  cancer" are different entries. Semantic near-matches are the
  [history layer's](../history_layer/history_layer.md) job, which is why the two
  sit next to each other in the fallback chain.
- **Not used by the server.** The FastAPI path substitutes
  `_UserCacheAdapter`, whose `lookup` always returns `None` because the
  PostgreSQL schema has no chunk-IDs column. This layer runs only in the TUI.
  See [AdpaterModule](../AdpaterModule/AdpaterModule.md).
