# history_layer — semantic query history

[← Back to BACKEND.md](../BACKEND.md) · [API reference](history_layer_API_DOCS.md)

Reuses a previous query's retrieval result when the new query means
approximately the same thing.

## The problem

The [cache layer](../cache_layer/cache_layer.md) keys on exact normalised text,
so "breast cancer screening" and "screening for breast cancer" miss each other
and both pay for a full ANN search. People rephrase constantly — especially
across turns of a conversation — and those rephrasings almost always want the
same passages.

## Design

Each entry stores the query's **embedding** alongside the chunk IDs it produced.
A lookup embeds the new query and walks the entries newest-first, returning the
first whose cosine similarity clears the threshold (0.80 by default, 0.90 in the
TUI wiring).

Newest-first matters: when several past queries are similar enough, the most
recent one is the best guess at what the user currently means.

```
  new query ──▶ embed ──▶ scan entries (newest first)
                             │
                    cosine ≥ threshold ──▶ reuse those chunk IDs
                             │
                          no match ──▶ fall through to ANN
```

### Bounded in two dimensions

- **Size** — a `deque(maxlen=32)`, so the oldest entry falls off the end.
- **Age** — `_evict_stale` drops anything older than `max_age_seconds` (1 hour)
  on every read and write, in memory and in SQLite together.

Both bounds exist because a stale reuse is worse than a cache miss: it returns
confidently wrong passages for a topic the user has moved on from.

### Storage

Embeddings persist as raw `float32` blobs (`numpy.tobytes()`), which is compact
and avoids a serialisation dependency. Vectors are normalised on the way in, so
lookup similarity is a plain dot product rather than a full cosine computation.

Entries are keyed by `(session_id, TopicKey)`, so sessions do not bleed into one
another.

## Trade-offs

- **Linear scan.** At 32 entries a brute-force walk is faster than any index
  would be, and the code stays trivial. This does not survive raising `max_size`
  by an order of magnitude.
- **Threshold is a blunt instrument.** Too low and unrelated questions reuse each
  other's passages; too high and it never fires. 0.80–0.90 was chosen empirically
  for `all-MiniLM-L6-v2`; a different embedding model needs re-tuning.
- **No verification.** A history hit is trusted without re-checking that the
  reused chunks actually suit the new query. The validator downstream is the
  safety net.

## Server-side status

`PgConversationHistory` implements the same interface for the FastAPI path but
keeps entries **in a per-process dict**, not PostgreSQL — the schema has no
column for chunk IDs. History is therefore lost on restart and not shared across
workers. See [AdpaterModule](../AdpaterModule/AdpaterModule.md).
