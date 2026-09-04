# wikipedia_scraper — corpus builder

[← Back to BACKEND.md](../BACKEND.md) · [API reference](wikipedia_scraper_API_DOCS.md)

A standalone tool that builds a topic-labelled text corpus from Wikipedia, for
developing and evaluating the retrieval pipeline.

## The problem

Working on retrieval quality needs a corpus with properties that are hard to
find together: large enough that ANN search behaves realistically, topically
structured so relevance is checkable, clean enough that chunking is not
dominated by markup, and freely redistributable.

Pointing the ingestion pipeline at a developer's own documents makes results
unreproducible and unshareable.

## Design

A six-stage pipeline, one module per stage:

```
  seeds ──▶ crawler ──▶ extractor ──▶ cleaner ──▶ topic_assigner ──▶ exporter
  (topic     (BFS via   (prose from   (strip      (label by         (write
   roots)     the API)   the page)     artefacts)   seed lineage)     corpus)
```

- **`seeds`** — curated starting pages per topic. Hand-picked because random
  starts wander into disambiguation pages and stubs.
- **`crawler`** — breadth-first over the MediaWiki API with a depth limit and a
  per-topic page cap, tracking visited pages so cross-links do not cause
  re-crawls. Uses the API rather than scraping HTML: it is the supported
  interface, returns clean structure, and respects rate limits.
- **`extractor`** — pulls prose, dropping infoboxes, navigation and references.
- **`cleaner`** — normalises whitespace and removes citation markers, so
  chunking is not derailed by `[12]` litter.
- **`topic_assigner`** — labels each page by the seed it descends from, giving
  retrieval evaluation a ground-truth topic per document.
- **`exporter`** — writes the corpus in the layout the ingestion pipeline reads.

Depth limiting is the key parameter: Wikipedia's link graph reaches everything
within a few hops, so an unbounded crawl from "Breast cancer" ends up in
unrelated subjects and destroys the topic labels.

## Relationship to the rest of the backend

None at runtime. It is a development tool that produces files; those files are
then ingested through the normal path. It has its own `config.py`, which
**shadows the project's root `config.py`** for anything importing it after the
scraper's `sys.path.insert` — a reason to run it as a script rather than import
it from application code.

`beautifulsoup4` is imported by this package but is not declared in
`requirements.txt`.

## Trade-offs

- **English Wikipedia only.**
- **No incremental crawl.** Each run starts fresh; there is no revision tracking.
- **Topic labels are structural, not semantic.** A page is labelled by the seed
  it was reached from, which is a good approximation and occasionally wrong.
