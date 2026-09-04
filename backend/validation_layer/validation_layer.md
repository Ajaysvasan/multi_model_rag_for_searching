# validation_layer — relevance gate

[← Back to BACKEND.md](../BACKEND.md) · [API reference](validation_layer_API_DOCS.md)

The last check before passages reach the model: are these actually about the
question, and if not, can a reformulated query do better?

## The problem

Reranking orders candidates but cannot tell you the whole set is bad. If a user
asks about something the corpus does not cover, the reranker dutifully returns
its least-bad passages. The model then either hallucinates from them or produces
a confused non-answer citing irrelevant sources.

Something has to be willing to say "none of this is good enough".

## Design

### Two signals, weighted by query shape

Each passage is scored on:

- **Keyword overlap** — the fraction of the query's content words (stopwords
  removed) that appear in the passage.
- **Embedding similarity** — cosine between query and passage vectors.

They are combined as a weighted sum, and the weights shift with query length:

| Query | Keyword weight | Embedding weight |
|---|---|---|
| ≤ 2 content words | 0.6 | 0.4 |
| > 2 content words | 0.4 | 0.6 |

The reasoning: for a two-word query like "BRCA mutations", the presence of those
exact terms is strong evidence. For a long natural-language question, individual
word matches mean less and the semantic vector is more trustworthy.

Passages scoring at or above `min_similarity` pass; the rest are rejected.

### Retry with reformulation

If *nothing* passes, the layer does not give up — it rewrites the query and
retrieves again, up to `max_retries` times:

```
  validate ──all rejected──▶ reformulate ──▶ retrieve ──▶ validate ──▶ …
       │                                                       │
     ≥1 passed                                          still nothing after N
       ▼                                                       ▼
    proceed                                        return the last result;
                                                   generator refuses honestly
```

Reformulation is deliberately crude — wrapping a bare phrase as "What is X?" or
prefixing "detailed information about" — because an LLM round-trip to rewrite
the query would cost more than the retrieval it is trying to fix.

### `LLMValidator`

A second, optional validator that asks a language model whether a passage is
relevant. Far more accurate and far more expensive; off by default and unused by
the default pipeline. It exists as an extension point.

## Trade-offs

- **`min_similarity` is the whole game.** Too high and valid answers get
  refused; too low and the gate does nothing. `Config.MIN_RELEVANCE_SCORE`
  (0.25) is the tuning knob.
- **Defaults are permissive.** `RetrievalValidator.__init__` defaults
  `min_similarity` and `min_keyword_overlap` to `0.0`, and the `x if x is not
  None else fallback` guards never fire because `0.0` is not `None`. Constructed
  with no arguments, the validator passes everything. `RetrievalEngine` relies on
  this being explicitly configured.
- **It re-embeds every candidate.** ~18 ms per query for 20 passages, on top of
  the reranker's own embedding pass. Negligible against generation, but it is
  duplicated work.
- **Keyword overlap is literal.** No stemming, no synonyms: "screening" and
  "screened" do not match. The embedding half is what covers for this.
