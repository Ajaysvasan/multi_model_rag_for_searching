"""
Cross-encoder reranker for improving retrieval relevance.

Uses a cross-encoder model to rerank retrieved chunks based on query-document
relevance scores. This provides more accurate ranking than bi-encoder similarity.
"""

import logging
import os
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

# Add parent to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from config import Config

logger = logging.getLogger("reranking")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


@dataclass
class RerankResult:
    """Result of reranking a single chunk."""
    chunk_id: str
    chunk_text: str
    score: float
    original_rank: int
    metadata: dict


class CrossEncoderReranker:
    """
    Reranks retrieved chunks using a cross-encoder model.
    
    Cross-encoders process query and document together, providing more
    accurate relevance scores than bi-encoder similarity.
    """
    
    def __init__(
        self,
        model_name: str = None,
        min_score: float = None,
        top_k: int = None,
    ):
        """
        Initialize the cross-encoder reranker.
        
        Args:
            model_name: HuggingFace model name for cross-encoder
            min_score: Minimum relevance score threshold (0-1)
            top_k: Maximum number of results to return after reranking
        """
        self.model_name = model_name or getattr(Config, 'RERANKER_MODEL', 'cross-encoder/ms-marco-MiniLM-L-6-v2')
        self.min_score = min_score if min_score is not None else getattr(Config, 'MIN_RELEVANCE_SCORE', 0.3)
        self.top_k = top_k or getattr(Config, 'RERANK_TOP_K', 5)
        
        self._model = None
        
    def _load_model(self):
        """Lazy load the cross-encoder model."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"Loading cross-encoder model: {self.model_name}")
                self._model = CrossEncoder(self.model_name)
                logger.info("Cross-encoder model loaded successfully")
            except ImportError:
                logger.error("sentence-transformers not installed. Install with: pip install sentence-transformers")
                raise
        return self._model
    
    def rerank(
        self,
        query: str,
        chunks: List[dict],
        text_key: str = "chunk_text",
    ) -> List[RerankResult]:
        """
        Rerank chunks based on query relevance.
        
        Args:
            query: The user's search query
            chunks: List of chunk dictionaries containing at minimum:
                   - chunk_id: Unique identifier
                   - text_key: The text content to compare
            text_key: Key in chunk dict containing text (default: "chunk_text")
            
        Returns:
            List of RerankResult sorted by relevance score (descending)
        """
        if not chunks:
            return []
        
        model = self._load_model()
        
        # Prepare query-document pairs for cross-encoder
        pairs = []
        for chunk in chunks:
            text = chunk.get(text_key, chunk.get("text", ""))
            pairs.append([query, text])
        
        # Get relevance scores
        logger.info(f"Reranking {len(chunks)} chunks with cross-encoder")
        scores = model.predict(pairs)
        
        # Normalize scores to 0-1 range using sigmoid if needed
        if isinstance(scores, np.ndarray):
            scores = scores.tolist()
        
        # Cross-encoder scores can vary widely, normalize with sigmoid
        normalized_scores = [self._sigmoid(s) for s in scores]
        
        # Create results with original ranks
        results = []
        for i, (chunk, score) in enumerate(zip(chunks, normalized_scores)):
            chunk_text = chunk.get(text_key, chunk.get("text", ""))
            results.append(RerankResult(
                chunk_id=chunk.get("chunk_id", f"chunk_{i}"),
                chunk_text=chunk_text,
                score=score,
                original_rank=i,
                metadata=chunk,
            ))
        
        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)
        
        # Apply minimum score filter
        results = [r for r in results if r.score >= self.min_score]
        
        # Apply top_k limit
        results = results[:self.top_k]
        
        logger.info(f"Reranking complete: {len(results)} chunks passed threshold")
        for i, r in enumerate(results[:3]):  # Log top 3
            logger.debug(f"  Rank {i+1}: score={r.score:.3f}, chunk_id={r.chunk_id[:20]}...")
        
        return results
    
    @staticmethod
    def _sigmoid(x: float) -> float:
        """Apply sigmoid to normalize scores."""
        return 1 / (1 + np.exp(-x))
    
    def get_reranked_ids(
        self,
        query: str,
        chunks: List[dict],
        text_key: str = "chunk_text",
    ) -> List[str]:
        """
        Convenience method to get just chunk IDs after reranking.
        
        Returns:
            List of chunk_ids sorted by relevance
        """
        results = self.rerank(query, chunks, text_key)
        return [r.chunk_id for r in results]


class LightweightReranker:
    """
    Lightweight reranker using bi-encoder embeddings for faster processing.
    
    Useful when cross-encoder is too slow for large candidate sets.
    First-stage reranking before cross-encoder.
    """
    
    def __init__(self, embedding_model=None, top_k: int = 20):
        """
        Args:
            embedding_model: SentenceTransformer model (reuses from retrieval)
            top_k: Number of candidates to keep after lightweight reranking
        """
        self.embedding_model = embedding_model
        self.top_k = top_k
        
    def rerank(
        self,
        query_embedding: np.ndarray,
        chunks: List[dict],
        chunk_embeddings: Optional[np.ndarray] = None,
    ) -> List[dict]:
        """
        Rerank using embedding similarity.
        
        Args:
            query_embedding: Query vector
            chunks: List of chunk dictionaries
            chunk_embeddings: Optional pre-computed chunk embeddings
            
        Returns:
            Top-K chunks sorted by similarity
        """
        if not chunks:
            return []
        
        # Compute embeddings if not provided
        if chunk_embeddings is None and self.embedding_model is not None:
            texts = [c.get("chunk_text", c.get("text", "")) for c in chunks]
            chunk_embeddings = self.embedding_model.encode(
                texts, 
                normalize_embeddings=True,
                show_progress_bar=False
            )
        
        if chunk_embeddings is None:
            logger.warning("No embeddings available for lightweight reranking")
            return chunks[:self.top_k]
        
        # Normalize query
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        
        # Compute similarities
        similarities = np.dot(chunk_embeddings, query_norm)
        
        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:self.top_k]
        
        return [chunks[i] for i in top_indices]
