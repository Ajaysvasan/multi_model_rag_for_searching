"""Regression tests for the "every query returns nothing" bug.

Cause: QueryProcessing left request framing in the query ("I need files
containing information about X"), and the MS MARCO cross-encoder scored every
passage far below min_score as a result -- measured -6.2 logit versus +6.5 for
the bare topic. rerank() then returned an empty list and the user was told no
information was found, even though ANN retrieval had returned the right passage.

These tests are pure string/logic checks: no model, no index, milliseconds.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from retrieval_layer.retrieval_engine import QueryProcessing


@pytest.fixture(scope="module")
def qp():
    return QueryProcessing(conversation_memory=None, embedding_model=None)


# Request framing that must be stripped so the reranker sees the topic.
@pytest.mark.parametrize(
    "query,expected",
    [
        ("I need files containing information about the cancer", "cancer"),
        ("I want to find documents about cancer", "cancer"),
        ("can you show me the documents about breast cancer", "breast cancer"),
        ("please find me files that mention mortality rate", "mortality rate"),
        ("do you have any papers on epidemiology", "epidemiology"),
        ("I'm looking for information about global health", "global health"),
        ("tell me about carcinogenesis", "carcinogenesis"),
        ("what is cancer", "cancer"),
        ("retrieve articles regarding life expectancy", "life expectancy"),
        ("list all reports discussing tumour growth", "tumour growth"),
    ],
)
def test_request_framing_is_stripped(qp, query, expected):
    assert qp._extract_query_intent(query).lower() == expected.lower()


# Content that happens to contain document nouns must survive intact. A document
# noun is only filler when a connector follows it, otherwise "the data
# protection act" would lose "data".
@pytest.mark.parametrize(
    "query,expected",
    [
        ("the data protection act", "data protection act"),
        ("what is the mortality rate in India", "mortality rate in India"),
        ("data about mortality rates", "mortality rates"),
        ("cancer", "cancer"),
        ("BRCA1 and BRCA2 mutations", "BRCA1 and BRCA2 mutations"),
        ("how does chemotherapy work", "how does chemotherapy work"),
    ],
)
def test_content_is_not_mangled(qp, query, expected):
    assert qp._extract_query_intent(query).lower() == expected.lower()


def test_never_returns_empty(qp):
    """Stripping must never consume the whole query."""
    for query in ("find me the documents about", "please", "show me", "what is"):
        result = qp._extract_query_intent(query)
        assert result, f"empty result for {query!r}"
        assert any(ch.isalpha() for ch in result)


def test_stripping_is_idempotent(qp):
    once = qp._extract_query_intent("I need files containing information about the cancer")
    assert qp._extract_query_intent(once) == once


class TestRerankerFloor:
    """rerank() must never turn a non-empty candidate set into nothing."""

    @staticmethod
    def _reranker(monkeypatch, scores):
        from reranking.reranker import CrossEncoderReranker

        rr = CrossEncoderReranker()
        # Stub the model so no checkpoint is downloaded or loaded.
        monkeypatch.setattr(rr, "_load_model", lambda: type("M", (), {"predict": lambda _s, _p: scores})())
        return rr

    def test_floor_keeps_top_ranked_when_all_below_threshold(self, monkeypatch):
        chunks = [{"chunk_id": f"c{i}", "chunk_text": f"passage {i}"} for i in range(5)]
        # Logits far below threshold, as a conversational query produces.
        rr = self._reranker(monkeypatch, [-9.0, -6.0, -8.0, -10.0, -7.0])
        results = rr.rerank("some query", chunks)

        assert results, "reranker returned nothing; the retrieval was discarded"
        assert len(results) == rr.min_keep
        # Still ordered best-first: -6.0 is the highest logit.
        assert results[0].chunk_id == "c1"

    def test_threshold_still_applies_when_something_passes(self, monkeypatch):
        chunks = [{"chunk_id": f"c{i}", "chunk_text": f"passage {i}"} for i in range(5)]
        # Two clearly relevant, three clearly not.
        rr = self._reranker(monkeypatch, [6.0, -9.0, 5.0, -10.0, -8.0])
        results = rr.rerank("some query", chunks)

        assert len(results) == 2
        assert {r.chunk_id for r in results} == {"c0", "c2"}

    def test_min_keep_zero_restores_strict_behaviour(self, monkeypatch):
        from reranking.reranker import CrossEncoderReranker

        chunks = [{"chunk_id": "c0", "chunk_text": "passage"}]
        rr = CrossEncoderReranker(min_keep=0)
        monkeypatch.setattr(rr, "_load_model", lambda: type("M", (), {"predict": lambda _s, _p: [-9.0]})())
        assert rr.rerank("q", chunks) == []

    def test_empty_input_returns_empty(self, monkeypatch):
        rr = self._reranker(monkeypatch, [])
        assert rr.rerank("q", []) == []
