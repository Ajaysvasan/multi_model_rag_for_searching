# retrieval_layer — API reference

[← Back to BACKEND.md](../BACKEND.md) · [Design notes](retrieval_layer.md)

## `QueryProcessing`

```python
from retrieval_layer.retrieval_engine import QueryProcessing

qp = QueryProcessing(conversation_memory=conv_memory, embedding_model=embed_model)

qp.preprocess_query("Can you find me a document about breast cancer screening?")
# -> "breast cancer screening"

qp.preprocess_query("what about risk factors?", session_id="sess-1")
# -> "breast cancer screening | ... what about risk factors?"
```

| Method | Returns | Notes |
|---|---|---|
| `preprocess_query(query, session_id="")` | `str` | Expansion then filler-stripping |
| `_extract_query_intent(query)` | `str` | Strips "find me a document that…" framing; returns the original if the result is under 3 characters |
| `_expand_with_context(query, session_id)` | `str` | Prepends recent turns for short or follow-up queries, gated at cosine 0.45 so unrelated questions are left alone |

## `RetrievalEngine`

```python
from retrieval_layer.retrieval_engine import RetrievalEngine

engine = RetrievalEngine(
    cache=cache,                  # .lookup(TopicKey) / .insert_new(TopicKey, ids)
    index=hnsw_index,             # .search(vector, k) -> list[str]
    embedding_model=embed_model,  # SentenceTransformer-compatible
    history=history,              # .find_similar(vec) / .add_or_update(...)
    ann_top_k=10,
    history_enabled=True,
    metadata_store=chunk_store,   # .get_by_ids(ids) -> list[dict]
    generator=generator,          # optional; lazily built if omitted
    conversation_memory=conv_mem, # optional
    reranker=None,                # pass an instance to pin it (see below)
    validator=None,
)
```

### Answering a question

```python
intent = engine.preprocess_query(user_question, session_id=session_id)
response = engine.retrieve_and_generate(user_question, intent, session_id=session_id)

print(response.answer)
print(response.retrieval_source)   # "cache" | "history" | "ann"
print(response.chunks_used)
for c in response.citations:
    print(c["id"], c["source_path"])
```

`RAGResponse` fields: `query`, `answer`, `citations`, `retrieval_source`,
`chunks_used`, `success`, `error`, `expanded_query`.

### Retrieval without generation

```python
ids = engine.retrieve("breast cancer screening")            # list[str]
rows = engine.retrieve_with_metadata("breast cancer screening")  # list[dict]

result = engine.retrieve_enhanced("breast cancer screening")
print(result.source, result.reranked, result.validated, result.validation_retries)
for chunk in result.chunks_with_metadata:
    print(chunk["chunk_id"], chunk["chunk_text"][:80])
```

`RetrievalResult` fields: `query`, `chunk_ids`, `chunks_with_metadata`,
`source`, `reranked`, `validated`, `validation_retries`.

### Disabling a subsystem

Pass it at construction. Assigning `None` to the private attribute does not
work — the property rebuilds it:

```python
class NoOpReranker:
    def rerank(self, query, chunks, text_key="chunk_text"):
        return [type("R", (), {"metadata": c})() for c in chunks]

engine = RetrievalEngine(..., reranker=NoOpReranker())
```

## Interfaces the engine expects

Anything satisfying these shapes works — this is how the PostgreSQL adapters in
`AdpaterModule/` substitute for the SQLite implementations.

| Collaborator | Required methods |
|---|---|
| `cache` | `lookup(TopicKey) -> TopicState \| None`, `insert_new(TopicKey, cached_chunk_ids)` |
| `index` | `search(vector, k) -> list[str]` |
| `history` | `find_similar(vec) -> list[str] \| None`, `add_or_update(TopicKey, vec, ids)` |
| `metadata_store` | `get_by_ids(list[str]) -> list[dict]` |
| `conversation_memory` | `get_recent_queries(session_id, max_queries)`, `get_context(session_id, max_turns)` |
| `generator` | `generate(query, chunks, conversation_context) -> GenerationResult` |
| `embedding_model` | `encode(text, normalize_embeddings=True)` |

## `QueryRouter`

```python
from retrieval_layer.retrieval_engine import QueryRouter

QueryRouter.infer_modality("show me the screenshot")   # "image"
QueryRouter.infer_modality("what does the report say") # "text"
QueryRouter.build_topic_key("breast cancer screening") # TopicKey(...)
```

`TopicKey` is the frozen, hashable `(topic_label, modality_filter,
retrieval_policy)` triple used as the cache and history key.
