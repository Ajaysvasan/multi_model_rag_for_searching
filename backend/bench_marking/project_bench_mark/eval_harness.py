"""Evaluation scaffolding for the real-data benchmark.

Kept separate from run_real_benchmark.py so the metrics and the stage proxies
can be unit-tested without importing the model, the database, or the pipeline.
"""

import math
import re


class DummyCache:
    """The 'cache disabled' arm of the ablation: a cache that can never hit."""

    def __init__(self):
        self.lookups = 0
        self.hits = 0

    def lookup(self, key):
        self.lookups += 1
        return None

    def insert_new(self, key, cached_chunk_ids):
        pass


class CountingCache:
    """Wraps the real cache and records whether it ever actually hit.

    The server-side cache adapter is a known stub (see AdpaterModule.md): the
    cache_topics table has no column for chunk ids, so lookup() always returns
    None.  Counting hits here means the report states that, instead of quietly
    crediting the cache for latency it never saved.
    """

    def __init__(self, inner):
        self._inner = inner
        self.lookups = 0
        self.hits = 0

    def lookup(self, key):
        self.lookups += 1
        state = self._inner.lookup(key)
        if state is not None:
            self.hits += 1
        return state

    def insert_new(self, key, cached_chunk_ids):
        return self._inner.insert_new(key, cached_chunk_ids)


class CountingHistory:
    def __init__(self, inner):
        self._inner = inner
        self.lookups = 0
        self.hits = 0

    def find_similar(self, vec):
        self.lookups += 1
        result = self._inner.find_similar(vec)
        if result is not None:
            self.hits += 1
        return result

    def add_or_update(self, *args, **kwargs):
        return self._inner.add_or_update(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class CountingReranker:
    """Proxy that records rerank() calls so a row can prove the stage ran."""

    def __init__(self, inner):
        self._inner = inner
        self.calls = 0

    def rerank(self, *args, **kwargs):
        self.calls += 1
        return self._inner.rerank(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class CountingValidator:
    def __init__(self, inner):
        self._inner = inner
        self.calls = 0

    def validate_with_retry(self, *args, **kwargs):
        self.calls += 1
        return self._inner.validate_with_retry(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def build_known_item_queries(chunks, n=8, min_words=12, window=10):
    """Return [(query, gold_chunk_id)] for known-item retrieval evaluation.

    Every query is generated from one specific chunk, so that chunk is a
    ground-truth positive obtained WITHOUT asking the system under test.  A
    configuration that fails to return it scores zero -- which is the whole
    point of a benchmark.

    The window is taken from a third of the way into the chunk rather than from
    its opening words.  The opening words are also roughly what the chunk reads
    and sorts as, which made the previous queries closer to an id lookup than to
    a question.  A word window rather than a sentence: the corpus chunks at 256
    characters, so the median chunk is ~18 words and often a single sentence.

    This is still an easier task than a real user question -- the report says so
    rather than papering over it.
    """
    usable = [c for c in chunks if len((c.text or "").split()) >= min_words]
    if not usable:
        return []

    out, seen = [], set()
    step = max(1, len(usable) // max(1, n))
    for chunk in usable[::step]:
        words = chunk.text.split()
        start = max(1, len(words) // 3)
        picked = words[start : start + window]
        if len(picked) < 5:
            picked = words[-window:]
        query = " ".join(picked).strip().strip(".,;:")
        if len(query.split()) < 5 or query.lower() in seen:
            continue
        seen.add(query.lower())
        out.append((query, chunk.id))
        if len(out) >= n:
            break
    return out


def known_item_metrics(retrieved_ids, gold_id, k=5):
    """Rank metrics against a positive the system under test did not supply.

    The previous harness built its gold set from the full pipeline's own
    output and then graded every configuration against it, so NDCG was 1.00 by
    construction -- it measured agreement with the full pipeline, not
    relevance.  With one graded-relevant document, NDCG reduces to
    1/log2(rank+1).
    """
    top_k = retrieved_ids[:k]
    rank = top_k.index(gold_id) + 1 if gold_id in top_k else 0
    return {
        "hit": 1.0 if rank else 0.0,
        "rr": 1.0 / rank if rank else 0.0,
        "ndcg": 1.0 / math.log2(rank + 1) if rank else 0.0,
    }


def pct(values, q):
    """Percentile without pulling in scipy; values need not be sorted."""
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))
    return ordered[idx]
