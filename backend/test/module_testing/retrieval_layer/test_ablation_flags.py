"""Regression tests for the retrieval ablation switches.

These exist because the benchmark harness used to "disable" a stage by
assigning ``engine._reranker = None``.  ``None`` is the not-built-yet sentinel
the property rebuilds from, so the stage came straight back -- and one of those
rebuilds landed inside a timed region and was reported as a 134x pipeline
slowdown.  Every configuration in the ablation table was therefore running the
full pipeline.  If these tests fail, that table is lying again.
"""

import os
import sys
from unittest.mock import patch

import pytest

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from retrieval_layer.retrieval_engine import RetrievalEngine


class _StubCache:
    def lookup(self, key):
        return None

    def insert_new(self, key, cached_chunk_ids):
        pass


class _StubHistory:
    def find_similar(self, vec):
        return None

    def add_or_update(self, key, vec, chunk_ids):
        pass


def make_engine(**kwargs):
    return RetrievalEngine(
        cache=_StubCache(),
        index=object(),
        embedding_model=object(),
        history=_StubHistory(),
        **kwargs,
    )


def test_disabled_reranker_stays_none():
    engine = make_engine(reranker_enabled=False)
    assert engine.reranker is None
    assert engine.reranker is None  # still None on a second access


def test_disabled_validator_stays_none():
    engine = make_engine(validator_enabled=False)
    assert engine.validator is None
    assert engine.validator is None


def test_disabled_reranker_is_never_constructed():
    """The point of the flag: no model load, not even once."""
    engine = make_engine(reranker_enabled=False)
    with patch("reranking.reranker.CrossEncoderReranker") as ctor:
        assert engine.reranker is None
        ctor.assert_not_called()


def test_disabled_validator_is_never_constructed():
    engine = make_engine(validator_enabled=False)
    with patch("validation_layer.validator.RetrievalValidator") as ctor:
        assert engine.validator is None
        ctor.assert_not_called()


def test_enabled_reranker_is_lazily_built_once():
    engine = make_engine(reranker_enabled=True)
    with patch("reranking.reranker.CrossEncoderReranker") as ctor:
        ctor.return_value = "built"
        assert engine.reranker == "built"
        assert engine.reranker == "built"
        assert ctor.call_count == 1  # cached, not rebuilt per access


def test_nulling_the_attribute_does_not_disable_the_stage():
    """Documents the trap the flags exist to replace.

    Anything that ablates by assigning None is measuring a rebuild, not an
    absence.  Asserted so the behaviour cannot change silently.
    """
    engine = make_engine(reranker_enabled=True)
    with patch("reranking.reranker.CrossEncoderReranker") as ctor:
        ctor.return_value = "rebuilt"
        engine._reranker = None
        assert engine.reranker == "rebuilt"
        ctor.assert_called_once()


def test_explicit_instance_is_used_as_given():
    sentinel = object()
    engine = make_engine(reranker=sentinel)
    assert engine.reranker is sentinel


def test_flags_default_to_enabled():
    """Ablation switches must not change production behaviour."""
    engine = make_engine()
    assert engine.reranker_enabled is True
    assert engine.validator_enabled is True
    assert engine.lightweight_rerank_enabled is True
