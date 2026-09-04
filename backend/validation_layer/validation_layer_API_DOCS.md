# validation_layer — API reference

[← Back to BACKEND.md](../BACKEND.md) · [Design notes](validation_layer.md)

## `RetrievalValidator`

```python
from validation_layer.validator import RetrievalValidator
from config import Config

validator = RetrievalValidator(
    embedding_model=embed_model,
    min_similarity=Config.MIN_RELEVANCE_SCORE,   # 0.25 -- set this explicitly
    min_keyword_overlap=0.2,
    max_retries=2,
)
```

> **Set `min_similarity` explicitly.** It defaults to `0.0`, and the internal
> fallback guard does not fire for `0.0`, so a default-constructed validator
> accepts every passage.

### One-shot validation

```python
result = validator.validate(
    query="What are the risk factors?",
    chunks=chunks,
    query_embedding=query_vec,       # optional; computed if omitted
)

print(result.is_valid, result.confidence)
for c in result.validated_chunks:
    print(c["chunk_id"], c["validation_score"])
```

`ValidationResult`: `is_valid`, `confidence` (mean score of survivors),
`validated_chunks`, `rejected_chunks`, `reason`, `retry_query`.

Both chunk lists are copies with a `validation_score` key added; originals are
untouched.

### Validation with retry

```python
def retrieve(q):
    vec = embed_model.encode(q, normalize_embeddings=True)
    return chunk_store.get_by_ids(index.search(vec, k=20))

result, attempts = validator.validate_with_retry(
    query="BRCA",
    retrieval_fn=retrieve,
    initial_chunks=chunks,           # optional; skips the first retrieval
    query_embedding=query_vec,
)
print(f"{len(result.validated_chunks)} passed after {attempts} retries")
```

`retrieval_fn` takes a query string and returns `list[dict]`. It is called only
when a round rejects everything.

## Scoring reference

```
combined = kw_weight * keyword_overlap + emb_weight * cosine_similarity
```

| Query content words | `kw_weight` | `emb_weight` |
|---|---|---|
| ≤ 2 | 0.6 | 0.4 |
| > 2 | 0.4 | 0.6 |

With no embedding model, `embedding_score` is a neutral `0.5` and the result is
driven entirely by keyword overlap.

## Helpers

```python
validator._extract_keywords("What are the main risk factors?")
# {'main', 'risk', 'factors'}   -- stopwords removed, 2+ letters, lowercased

validator._compute_keyword_overlap({"risk", "factors"}, "risk factors include obesity")
# 1.0
```

An empty keyword set scores a neutral `0.5` rather than dividing by zero.

## `LLMValidator` (optional)

```python
from validation_layer.validator import LLMValidator

llm_validator = LLMValidator(llm_client=my_client)
is_relevant, confidence = llm_validator.validate_chunk(query, chunk_text)
```

`llm_client` must expose `generate_content(prompt) -> obj` with a `.text`
attribute. With no client it returns `(True, 0.5)` — accept by default. Failures
also default to accepting, so this can never block the pipeline.

## Wiring into the engine

```python
engine = RetrievalEngine(
    ...,
    validator=RetrievalValidator(
        embedding_model=embed_model,
        min_similarity=0.25,
        max_retries=2,
    ),
)
```

As with the reranker, `engine._validator = None` does not disable validation —
the lazy property rebuilds it. Pass an instance whose `validate_with_retry`
returns everything if you need a pass-through.

## Tuning

| Parameter | Default | Raising it |
|---|---|---|
| `min_similarity` | `Config.MIN_RELEVANCE_SCORE` = 0.25 | Stricter; more refusals, less noise |
| `max_retries` | `Config.MAX_RETRIES` = 2 | More reformulation attempts, slower failures |
| `min_keyword_overlap` | 0.2 | Currently unused in scoring |
