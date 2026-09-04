# reranking — API reference

[← Back to BACKEND.md](../BACKEND.md) · [Design notes](reranking.md)

## `CrossEncoderReranker`

```python
from reranking.reranker import CrossEncoderReranker

reranker = CrossEncoderReranker(
    model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",  # default: Config.RERANKER_MODEL
    min_score=0.3,                                       # sigmoid-squashed cutoff
    top_k=5,                                             # default: Config.RERANK_TOP_K
    min_keep=3,                                          # floor when nothing clears min_score
)

chunks = [
    {"chunk_id": "c1", "chunk_text": "Mammography is the primary screening tool."},
    {"chunk_id": "c2", "chunk_text": "The Fourier transform decomposes a signal."},
    {"chunk_id": "c3", "chunk_text": "Screening is advised every two years."},
]

results = reranker.rerank("How is breast cancer screened?", chunks)
for r in results:
    print(f"{r.score:.3f}  rank {r.original_rank} -> {r.chunk_id}")
```

`RerankResult`: `chunk_id`, `chunk_text`, `score` (0–1), `original_rank`,
`metadata` (the original dict, unmodified).

| Method | Returns |
|---|---|
| `rerank(query, chunks, text_key="chunk_text")` | `list[RerankResult]`, descending score, filtered and truncated |
| `get_reranked_ids(query, chunks, text_key=...)` | `list[str]` of chunk IDs only |

The model loads on first `rerank()`, not at construction — expect ~6 s once.

Text lookup falls back from `text_key` to `"text"`, so both chunk shapes work.

## `LightweightReranker`

```python
from reranking.reranker import LightweightReranker

light = LightweightReranker(embedding_model=embed_model, top_k=10)

query_vec = embed_model.encode(query, normalize_embeddings=True)
reordered = light.rerank(query_vec, chunks)     # list[dict], not RerankResult
```

Takes a **query vector**, not a query string. Passage embeddings are computed on
demand unless supplied:

```python
reordered = light.rerank(query_vec, chunks, chunk_embeddings=precomputed)
```

With no embedding model and no precomputed vectors it degrades to
`chunks[:top_k]` and logs a warning.

## Wiring into the engine

```python
from retrieval_layer.retrieval_engine import RetrievalEngine
from reranking.reranker import CrossEncoderReranker

engine = RetrievalEngine(..., reranker=CrossEncoderReranker(min_score=0.4))
```

Passing it at construction pins the instance. Assigning
`engine._reranker = None` does **not** disable reranking — `RetrievalEngine.reranker`
is a lazy property that rebuilds it on next access. To disable, pass a
pass-through:

```python
class NoOpReranker:
    def rerank(self, query, chunks, text_key="chunk_text"):
        return [type("R", (), {"metadata": c, "score": 1.0})() for c in chunks]
```

## Tuning

| Parameter | Default | Effect of raising it |
|---|---|---|
| `min_score` | 0.3 | Fewer, more relevant passages |
| `min_keep` | 3 | Candidates kept when nothing clears `min_score`; `0` restores strict filtering |
| `top_k` | `Config.RERANK_TOP_K` (5) | Longer prompts, slower prefill |
| `Config.ANN_TOP_K` | 10 | Doubled before reranking, so more candidates to choose from and more cross-encoder work |

`rerank()` returns an empty list only when it was given no candidates. When
candidates exist but none clears `min_score`, the top `min_keep` are returned
with a logged warning — a very low best score usually means the query still
contains request phrasing that `_extract_query_intent` did not strip. The
generator still refuses when those passages do not answer the question.
