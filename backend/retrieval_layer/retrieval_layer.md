# retrieval_layer — orchestration

[← Back to BACKEND.md](../BACKEND.md) · [API reference](retrieval_layer_API_DOCS.md)

The conductor. Turns a raw user question into a cited answer by driving the
cache, history, vector index, reranker, validator, and generator in order.

## The problem

A naive RAG loop is "embed the question, take the top-k, stuff them in a
prompt". It fails in three ways:

1. **Questions are not queries.** "Can you find me a document which talks about
   breast cancer screening?" embeds badly — half the vector encodes the request
   framing rather than the subject.
2. **Follow-ups lose their subject.** "What about screening?" means nothing
   standalone, but everything given the previous turn.
3. **ANN is approximate.** Top-k always returns k results, however irrelevant.
   Without a downstream filter, the model is handed noise and either hallucinates
   from it or refuses.

## Design

Two classes, deliberately separate:

- **`QueryProcessing`** — pure text work: filler-phrase stripping and
  history-aware expansion. No index, no model. Kept apart so it can be reused by
  the TUI and tested without loading anything.
- **`RetrievalEngine`** — extends it and owns the retrieval chain and generation
  call.

### The fallback chain

```
  query ─▶ topic cache ──hit──▶ chunk IDs
             │ miss
             ▼
           history  ────hit──▶ chunk IDs      (cosine ≥ 0.80 against past queries)
             │ miss
             ▼
           FAISS ANN ─────────▶ chunk IDs      (ann_top_k × 2 candidates)
```

Cheapest first. A cache hit skips embedding entirely; a history hit reuses a
previous query's result set; only a double miss touches the index. Each stage
writes its result back into the cheaper stages, so a repeated question gets
progressively faster.

The query is embedded **once** per request and that vector is reused for the
history lookup, the ANN search, lightweight reranking, and validation.

### Post-retrieval filtering

Candidates are over-fetched (`ann_top_k × 2`) and then narrowed:

| Stage | On the ANN path | On a cache/history hit |
|---|---|---|
| Rerank | Cross-encoder, joint query-passage scoring | Bi-encoder cosine (`LightweightReranker`) |
| Validate | Keyword overlap + embedding similarity, with query-reformulation retry | Same |

The asymmetry is intentional: a cross-encoder costs ~19 ms for 20 candidates,
which is worth paying on a fresh search but not on a cached set that was already
ranked when it was first computed.

Reranker and validator are **lazy properties**. They construct on first access,
so a process that never reaches the ANN path never pays the ~6 s cross-encoder
load.

> **Consequence worth knowing.** Because they are lazy properties, setting
> `engine._reranker = None` does not disable reranking — the property rebuilds
> it on next access. Ablation benchmarks that toggle subsystems that way are
> measuring nothing. Pass `reranker=…`/`validator=…` at construction instead.

### Missing chunk text

`_get_chunks_with_text` will **not** re-read the source file when a chunk's
stored text is missing. Offsets refer to *normalised* text, so seeking into the
raw PDF would return misaligned bytes and the model would confidently cite
nonsense. The chunk is dropped with a warning pointing at `backfill_chunks.py`.
Losing a passage is recoverable; citing the wrong bytes is not.

## Data flow

`retrieve_and_generate` returns a `RAGResponse` carrying the answer, the
citations, which stage served the retrieval (`cache` / `history` / `ann`), how
many chunks were used, and the expanded query when expansion fired — enough to
debug a bad answer without re-running it.

### Why query cleaning is load-bearing

The reranker is a MS MARCO passage-ranking cross-encoder: it scores *"does this
passage answer this query"*. Leave the request framing in and it answers
correctly but uselessly — a passage about cancer does not answer a question
about *needing files*:

| Query reaching the reranker | Raw logit | Sigmoid |
|---|---|---|
| `I need files containing information about the cancer` | −6.214 | 0.002 |
| `cancer` | +6.486 | 0.998 |

With `min_score` at 0.3 the first form drops every candidate and the user is
told nothing was found, even though ANN retrieval returned exactly the right
passage. Filler-stripping is therefore not a nicety — it is what keeps the
reranker calibrated.

Two defences, because either alone is brittle:

1. `_extract_query_intent` strips framing repeatedly until stable, with a
   connector requirement on document nouns so "the data protection act" is not
   mangled into "protection act".
2. `CrossEncoderReranker` keeps its top `min_keep` candidates when *nothing*
   clears the threshold. Relevance is then judged by the validator and the
   generator, which refuse honestly, instead of by a threshold calibrated for a
   different query distribution.

## Known issues

- `_expand_with_context` is implemented twice, in `QueryProcessing` and again in
  `RetrievalEngine`, with slightly different embedding calls. `main.py` invokes
  both paths, so a short follow-up can get its history prefix applied twice.
- `RetrievalEngine` subclasses `QueryProcessing` but sets its attributes
  directly instead of calling `super().__init__`.
