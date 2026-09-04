# reranking — relevance reordering

[← Back to BACKEND.md](../BACKEND.md) · [API reference](reranking_API_DOCS.md)

Reorders ANN candidates by actually reading them against the query, and drops
the ones that do not belong.

## The problem

FAISS returns the *k* nearest vectors, always. Nearest is not the same as
relevant: ask for 20 and you get 20, even when only three passages touch the
subject. The embedding is also computed for query and passage independently, so
it cannot notice that a passage mentions the query's terms in an unrelated sense.

Feeding those 20 to the model is expensive (prefill scales with prompt length)
and harmful (irrelevant passages invite hallucination and dilute citations).

## Design

Two rerankers with different cost/quality profiles, chosen by which retrieval
stage produced the candidates.

### `CrossEncoderReranker` — the accurate one

A cross-encoder (`ms-marco-MiniLM-L-6-v2`) takes the query and passage
**together** as one input and emits a single relevance score. Because the two
attend to each other, it catches term-sense mismatches a bi-encoder cannot.

The cost is that it cannot be precomputed: every (query, passage) pair is a
forward pass. Scores are squashed through a sigmoid to a 0–1 range, sorted, cut
at `min_score`, and truncated to `top_k`.

Measured: ~19 ms for 20 candidates on CPU, plus a one-time ~6 s model load.

### `LightweightReranker` — the cheap one

Bi-encoder cosine against the already-computed query vector. No new model, no
joint scoring — just a dot product against passage embeddings. Used on
cache and history hits, where the set was already ranked when first computed and
only needs re-ordering.

### Which runs when

```
  source == "ann"  ──▶ CrossEncoderReranker   (fresh candidates, worth the cost)
  cache/history hit ─▶ LightweightReranker    (already ranked once)
```

Lazy loading means a process that only ever hits cache never pays the
cross-encoder load.

## Trade-offs

- **Over-fetch then cut.** Retrieval asks for `ann_top_k × 2` so the reranker
  has something to discard. Reranking a set of exactly `k` can only reorder.
- **`min_score` is a real filter, with a floor.** Everything below 0.3 is
  dropped — but if that would leave *nothing*, the top `min_keep` (3) candidates
  are kept anyway and a warning is logged. Scores are calibrated for short
  search-style queries; a conversational one scores every passage far below
  threshold even when the top hit is exactly right, and returning an empty list
  turns a correct retrieval into "no information found". Relevance is then
  settled downstream by the validator and the generator, which refuse honestly.
  Set `min_keep=0` for the old strict behaviour.
- **Cross-encoders do not scale.** Cost is linear in candidates. At 20 that is
  fine; at 1000 it would dominate the query. The ANN stage exists to keep the
  candidate set small enough for this to be affordable.
- **Return types differ.** `CrossEncoderReranker.rerank` returns
  `RerankResult` objects; `LightweightReranker.rerank` returns plain dicts. The
  engine unwraps `.metadata` in the first case. Worth knowing when substituting
  one for the other.
