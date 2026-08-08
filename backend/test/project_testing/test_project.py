"""
Project-level tests — Normal + Stress (using real data where available)
Run with:  python -m pytest test/project_testing/test_project.py -v
"""
import gc
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Path setup
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, BACKEND_ROOT)

from config import Config
from generation_layer.generator import (
    AnswerGenerator,
    Citation,
    GenerationResult,
    LlamaGenerator,
    MmapGenerator,
)

try:
    import download_model
except ImportError:
    download_model = None


# =========================================================================
# SECTION 1 — NORMAL TESTS
# =========================================================================

class TestConfig:
    def test_generation_model_is_mistral_7b(self):
        assert "Mistral-7B" in Config.GENERATION_MODEL

    def test_default_model_matches_generation_model(self):
        assert Config.DEFAULT_MODEL == Config.GENERATION_MODEL

    def test_embedding_model_is_set(self):
        assert Config.EMBED_MODEL_NAME == "sentence-transformers/all-MiniLM-L6-v2"

    def test_reranker_model_is_set(self):
        assert Config.RERANKER_MODEL == "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def test_ann_top_k_reasonable(self):
        assert 5 <= Config.ANN_TOP_K <= 50

    def test_min_relevance_score_reasonable(self):
        assert 0.1 <= Config.MIN_RELEVANCE_SCORE <= 0.8


class TestModelFile:
    def test_model_gguf_exists(self):
        model_path = Path(BACKEND_ROOT) / "models" / Config.GENERATION_MODEL_FILE
        assert model_path.exists(), f"Model file not found at {model_path}"

    def test_model_file_not_truncated(self):
        model_path = Path(BACKEND_ROOT) / "models" / Config.GENERATION_MODEL_FILE
        if model_path.exists():
            size_gb = model_path.stat().st_size / (1024 ** 3)
            assert size_gb > 3, f"Model file too small ({size_gb:.2f} GB), likely truncated"


class TestGeneratorImports:
    def test_llama_generator_importable(self):
        assert LlamaGenerator is not None

    def test_mmap_generator_importable(self):
        assert MmapGenerator is not None

    def test_answer_generator_alias(self):
        assert AnswerGenerator is not None

    def test_generation_result_dataclass(self):
        res = GenerationResult(
            answer="test", citations=[], raw_response="raw",
            model_used="mistral", tokens_used=10, success=True, error=None,
        )
        assert res.answer == "test"
        assert res.success is True
        assert res.tokens_used == 10

    def test_citation_dataclass(self):
        cit = Citation(
            citation_id=1, chunk_id="abc", source_path="doc.pdf",
            chunk_text="hello world", start_offset=0, end_offset=11,
            relevance_score=0.92,
        )
        assert cit.citation_id == 1
        assert cit.chunk_id == "abc"
        assert cit.relevance_score == 0.92

    def test_download_model_importable(self):
        assert download_model is not None, "download_model.py could not be imported"


class TestCleanResponse:
    def test_strips_references_section(self):
        text = "The answer is 42.\nReferences:\n[1] Fake source"
        result = LlamaGenerator._clean_response(text)
        assert "References:" not in result

    def test_strips_bibliography_section(self):
        text = "The answer.\nBibliography:\nSmith 2023"
        result = LlamaGenerator._clean_response(text)
        assert "Bibliography:" not in result

    def test_strips_urls(self):
        text = "See http://example.com for details"
        result = LlamaGenerator._clean_response(text)
        assert "http://" not in result

    def test_strips_apa_citations(self):
        text = "According to (Smith & Doe, 2023) this is true."
        result = LlamaGenerator._clean_response(text)
        assert "2023" not in result

    def test_preserves_clean_text(self):
        text = "Paris is the capital of France."
        result = LlamaGenerator._clean_response(text)
        assert result == text


class TestRefusalDetection:
    def test_refusal_detected(self):
        assert LlamaGenerator._is_refusal("I couldn't find the answer") is True

    def test_refusal_detected_variant(self):
        assert LlamaGenerator._is_refusal("There is no relevant information") is True

    def test_normal_text_not_refusal(self):
        assert LlamaGenerator._is_refusal("The capital of France is Paris.") is False


class TestCitationExtraction:
    def test_extracts_single_citation(self):
        assert LlamaGenerator._extract_cited_indices("Answer [1]") == {1}

    def test_extracts_multiple_citations(self):
        assert LlamaGenerator._extract_cited_indices("A [1] B [3] C [5]") == {1, 3, 5}

    def test_no_citations_returns_empty(self):
        assert LlamaGenerator._extract_cited_indices("No citations here") == set()

    def test_duplicate_citations_deduplicated(self):
        assert LlamaGenerator._extract_cited_indices("[1] again [1]") == {1}


# =========================================================================
# SECTION 2 — STRESS TESTS (using real data from the database)
# =========================================================================

class TestStressRealData:
    """
    These tests use real chunks from the database when available,
    falling back to realistic synthetic text if the DB is unreachable.
    """

    @staticmethod
    def _get_real_chunks(limit=50):
        """Try to load real chunks from the database."""
        try:
            from data_models.session import SessionLocal
            from data_models.users import User
            from data_models.chunks import Chunk
            db = SessionLocal()
            user = db.query(User).first()
            if not user:
                db.close()
                return None
            chunks = db.query(Chunk).filter(Chunk.user_id == user.id).limit(limit).all()
            texts = [c.text for c in chunks if c.text and len(c.text) > 10]
            db.close()
            return texts if texts else None
        except Exception:
            return None

    def test_stress_clean_response_on_large_real_text(self):
        """Run _clean_response on a large body of real text."""
        texts = self._get_real_chunks(50)
        if texts:
            big_text = " ".join(texts)[:50000]
        else:
            big_text = "Real data unavailable. " * 2500
        t0 = time.time()
        result = LlamaGenerator._clean_response(big_text)
        elapsed = time.time() - t0
        assert elapsed < 5, f"_clean_response took {elapsed:.2f}s on 50KB"
        assert isinstance(result, str)

    def test_stress_100k_refusal_checks_on_real_text(self):
        """Run _is_refusal 100K times on a real chunk of text."""
        texts = self._get_real_chunks(1)
        sample = texts[0] if texts else "Normal text without refusal indicators."
        t0 = time.time()
        for _ in range(100_000):
            LlamaGenerator._is_refusal(sample)
        elapsed = time.time() - t0
        assert elapsed < 10, f"100K refusal checks took {elapsed:.2f}s"

    def test_stress_50k_citation_objects(self):
        """Create 50K Citation objects rapidly."""
        t0 = time.time()
        citations = [
            Citation(i, f"chunk_{i}", "/path/doc.pdf", "text...", 0, 100, 0.9)
            for i in range(50_000)
        ]
        elapsed = time.time() - t0
        assert len(citations) == 50_000
        assert elapsed < 10

    def test_stress_10k_generation_results(self):
        """Create 10K GenerationResult objects rapidly."""
        t0 = time.time()
        results = [
            GenerationResult(
                answer=f"Answer {i}", citations=[], raw_response="raw",
                model_used="mistral", tokens_used=i, success=True,
            )
            for i in range(10_000)
        ]
        elapsed = time.time() - t0
        assert len(results) == 10_000
        assert elapsed < 5

    def test_stress_extract_cited_indices_on_large_text(self):
        """Extract citations from a large body of text with many [N] markers."""
        # Build realistic text with many citation markers
        parts = []
        for i in range(500):
            parts.append(f"This fact [{i % 20 + 1}] is important.")
        big_text = " ".join(parts)
        t0 = time.time()
        result = LlamaGenerator._extract_cited_indices(big_text)
        elapsed = time.time() - t0
        assert elapsed < 1
        assert len(result) == 20  # [1] through [20]

    def test_stress_clean_response_on_real_db_text(self):
        """Run _clean_response on a large body of real text from the database."""
        texts = self._get_real_chunks(50)
        if texts:
            # Use ALL real text concatenated (~50KB)
            big_text = " ".join(texts)
            assert len(big_text) > 1000, "Real text too short for meaningful test"
        else:
            pytest.skip("No real chunks available in database")
        t0 = time.time()
        result = LlamaGenerator._clean_response(big_text)
        elapsed = time.time() - t0
        assert elapsed < 5, f"_clean_response took {elapsed:.2f}s on {len(big_text)} chars"
        assert isinstance(result, str)
        assert len(result) > 0

    def test_stress_extract_citations_on_real_text(self):
        """Run _extract_cited_indices on real DB text with injected citations."""
        texts = self._get_real_chunks(20)
        if not texts:
            pytest.skip("No real chunks available in database")
        # Inject realistic citation markers into real text
        annotated = ""
        for i, t in enumerate(texts):
            annotated += f"{t} [{i+1}] "
        t0 = time.time()
        for _ in range(1000):
            result = LlamaGenerator._extract_cited_indices(annotated)
        elapsed = time.time() - t0
        assert elapsed < 5
        assert len(result) == len(texts)

