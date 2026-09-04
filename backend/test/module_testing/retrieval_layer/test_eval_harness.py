"""Tests for the benchmark's evaluation scaffolding.

A benchmark is code, and its metrics can be wrong in exactly the way the code
under test can.  These pin the two properties that matter: the metrics must be
able to report failure, and the stage proxies must count honestly.
"""

import os
import sys

import pytest

HARNESS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../bench_marking/project_bench_mark")
)
if HARNESS_DIR not in sys.path:
    sys.path.insert(0, HARNESS_DIR)

from eval_harness import (
    CountingCache,
    CountingReranker,
    DummyCache,
    build_known_item_queries,
    known_item_metrics,
    pct,
)


class _Chunk:
    def __init__(self, cid, text):
        self.id = cid
        self.text = text


LONG = (
    "Breast cancer is a type of cancer that originates from breast tissue. "
    "It most commonly develops in the inner lining of milk ducts. "
    "Screening can be instrumental in detecting the disease at an early stage. "
    "Risk factors include age, family history and hormone exposure. "
    "Treatment usually combines surgery with radiation or chemotherapy. "
    "Outcomes depend strongly on the stage at which it was found."
)


def test_metrics_reward_rank_one():
    m = known_item_metrics(["a", "b", "c"], "a")
    assert m["hit"] == 1.0
    assert m["rr"] == 1.0
    assert m["ndcg"] == 1.0


def test_metrics_decay_with_rank():
    first = known_item_metrics(["a", "b", "c"], "a")
    third = known_item_metrics(["x", "y", "a"], "a")
    assert third["hit"] == 1.0
    assert third["rr"] == pytest.approx(1 / 3)
    assert third["ndcg"] < first["ndcg"]


def test_metrics_can_score_zero():
    """The property the old gold labels made impossible."""
    m = known_item_metrics(["x", "y", "z"], "a")
    assert m == {"hit": 0.0, "rr": 0.0, "ndcg": 0.0}


def test_metrics_respect_the_cutoff():
    ranked = ["x", "y", "z", "w", "v", "a"]
    assert known_item_metrics(ranked, "a", k=5)["hit"] == 0.0
    assert known_item_metrics(ranked, "a", k=6)["hit"] == 1.0


def test_metrics_on_empty_retrieval():
    assert known_item_metrics([], "a")["hit"] == 0.0


def test_queries_carry_their_source_chunk():
    chunks = [_Chunk(f"c{i}", LONG) for i in range(6)]
    queries = build_known_item_queries(chunks, n=3)
    assert queries
    for text, gold in queries:
        assert isinstance(text, str) and text
        assert gold in {c.id for c in chunks}


def test_queries_skip_chunks_that_are_too_short():
    assert build_known_item_queries([_Chunk("c0", "too short")], n=3) == []


def test_queries_are_not_the_opening_words():
    """Opening words are near-identical to how the chunk is stored and sorted,
    which made the old queries an id lookup rather than a question."""
    chunks = [_Chunk("c0", LONG)]
    (text, _gold), = build_known_item_queries(chunks, n=1)
    assert not LONG.startswith(text)


def test_queries_work_on_short_real_world_chunks():
    """Regression: the corpus chunks at 256 characters, so the median chunk is
    ~18 words and usually one sentence. A sentence-based picker requiring 40+
    words per chunk found zero queries against the live database."""
    texts = [
        "Signs of breast cancer may include a lump in the breast or a change in breast shape",
        "Risk factors include obesity a lack of physical exercise and alcohol consumption",
        "Screening can be instrumental in detecting the disease at an early stage of growth",
    ]
    chunks = [_Chunk(f"c{i}", t) for i, t in enumerate(texts)]
    queries = build_known_item_queries(chunks, n=3)
    assert len(queries) == 3
    assert {g for _, g in queries} == {"c0", "c1", "c2"}


def test_queries_skip_chunks_below_the_word_floor():
    chunks = [_Chunk("c0", " ".join(["word"] * 11))]
    assert build_known_item_queries(chunks, n=1, min_words=12) == []


def test_queries_are_unique():
    chunks = [_Chunk(f"c{i}", LONG) for i in range(5)]
    texts = [q for q, _ in build_known_item_queries(chunks, n=5)]
    assert len(texts) == len(set(texts))


def test_counting_reranker_counts_and_delegates():
    class Inner:
        def rerank(self, *a, **kw):
            return ["ranked"]

        def other(self):
            return "delegated"

    proxy = CountingReranker(Inner())
    assert proxy.calls == 0
    assert proxy.rerank("q", []) == ["ranked"]
    assert proxy.calls == 1
    assert proxy.other() == "delegated"


def test_counting_cache_separates_lookups_from_hits():
    class AlwaysMisses:
        def lookup(self, key):
            return None

        def insert_new(self, key, cached_chunk_ids):
            pass

    proxy = CountingCache(AlwaysMisses())
    for _ in range(3):
        proxy.lookup("k")
    assert (proxy.lookups, proxy.hits) == (3, 0)


def test_dummy_cache_never_hits():
    cache = DummyCache()
    assert cache.lookup("k") is None
    assert cache.hits == 0
    assert cache.lookups == 1


def test_pct_picks_order_statistics():
    values = [0.5, 0.1, 0.4, 0.2, 0.3]
    assert pct(values, 0.5) == 0.3
    assert pct(values, 0.0) == 0.1
    assert pct(values, 1.0) == 0.5
    assert pct([], 0.5) == 0.0
