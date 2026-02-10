"""
Retrieval Validation Layer.

Validates that retrieved chunks are semantically relevant to the query.
If validation fails, triggers re-retrieval with modified parameters.
"""

import logging
import os
import sys
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from config import Config

logger = logging.getLogger("validation")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


@dataclass
class ValidationResult:
    """Result of chunk validation."""
    is_valid: bool
    confidence: float
    validated_chunks: List[dict]
    rejected_chunks: List[dict]
    reason: Optional[str] = None
    retry_query: Optional[str] = None


class RetrievalValidator:
    """
    Validates retrieved chunks for relevance to the query.
    
    Uses multiple strategies:
    1. Embedding similarity threshold
    2. Keyword overlap check
    3. Optional LLM-based verification for edge cases
    """
    
    def __init__(
        self,
        embedding_model=None,
        min_similarity: float = None,
        min_keyword_overlap: float = None,
        max_retries: int = None,
        use_llm_verification: bool = False,
    ):
        """
        Args:
            embedding_model: SentenceTransformer model for similarity computation
            min_similarity: Minimum cosine similarity threshold (0-1)
            min_keyword_overlap: Minimum fraction of query keywords in chunk
            max_retries: Maximum re-retrieval attempts
            use_llm_verification: Whether to use LLM for final verification
        """
        self.embedding_model = embedding_model
        self.min_similarity = min_similarity if min_similarity is not None else getattr(Config, 'MIN_RELEVANCE_SCORE', 0.3)
        self.min_keyword_overlap = min_keyword_overlap if min_keyword_overlap is not None else 0.2
        self.max_retries = max_retries or getattr(Config, 'MAX_RETRIES', 2)
        self.use_llm_verification = use_llm_verification
        
    def validate(
        self,
        query: str,
        chunks: List[dict],
        query_embedding: Optional[np.ndarray] = None,
    ) -> ValidationResult:
        """
        Validate that chunks are relevant to the query.
        
        Args:
            query: Original user query
            chunks: List of chunk dictionaries with 'chunk_text' or 'text' key
            query_embedding: Optional pre-computed query embedding
            
        Returns:
            ValidationResult with validated/rejected chunks
        """
        if not chunks:
            return ValidationResult(
                is_valid=False,
                confidence=0.0,
                validated_chunks=[],
                rejected_chunks=[],
                reason="No chunks to validate",
            )
        
        validated = []
        rejected = []
        
        # Compute query embedding if not provided
        if query_embedding is None and self.embedding_model is not None:
            query_embedding = self.embedding_model.encode(
                query, 
                normalize_embeddings=True
            )
        
        # Extract query keywords for keyword overlap check
        query_keywords = self._extract_keywords(query)
        
        for chunk in chunks:
            chunk_text = chunk.get("chunk_text", chunk.get("text", ""))
            
            # Strategy 1: Keyword overlap
            keyword_score = self._compute_keyword_overlap(query_keywords, chunk_text)
            
            # Strategy 2: Embedding similarity (if available)
            embedding_score = 0.5  # Default neutral score
            if query_embedding is not None and self.embedding_model is not None:
                chunk_embedding = self.embedding_model.encode(
                    chunk_text,
                    normalize_embeddings=True
                )
                embedding_score = float(np.dot(query_embedding, chunk_embedding))
            
            # Combined score (weighted average)
            combined_score = 0.4 * keyword_score + 0.6 * embedding_score
            
            # Add score to chunk metadata
            chunk_with_score = {**chunk, "validation_score": combined_score}
            
            if combined_score >= self.min_similarity:
                validated.append(chunk_with_score)
            else:
                rejected.append(chunk_with_score)
        
        # Determine overall validity
        is_valid = len(validated) > 0
        avg_confidence = np.mean([c["validation_score"] for c in validated]) if validated else 0.0
        
        # Generate retry query if validation failed
        retry_query = None
        if not is_valid:
            retry_query = self._generate_retry_query(query, rejected)
        
        logger.info(
            f"Validation: {len(validated)}/{len(chunks)} chunks passed, "
            f"confidence={avg_confidence:.2f}"
        )
        
        return ValidationResult(
            is_valid=is_valid,
            confidence=float(avg_confidence),
            validated_chunks=validated,
            rejected_chunks=rejected,
            reason="Insufficient relevance" if not is_valid else None,
            retry_query=retry_query,
        )
    
    def validate_with_retry(
        self,
        query: str,
        retrieval_fn: Callable[[str], List[dict]],
        initial_chunks: Optional[List[dict]] = None,
        query_embedding: Optional[np.ndarray] = None,
    ) -> Tuple[ValidationResult, int]:
        """
        Validate chunks with automatic re-retrieval on failure.
        
        Args:
            query: Original query
            retrieval_fn: Function that takes query and returns chunks
            initial_chunks: Pre-retrieved chunks (optional)
            query_embedding: Pre-computed query embedding
            
        Returns:
            Tuple of (ValidationResult, number of retries used)
        """
        current_query = query
        chunks = initial_chunks or retrieval_fn(query)
        
        for attempt in range(self.max_retries + 1):
            result = self.validate(current_query, chunks, query_embedding)
            
            if result.is_valid:
                return result, attempt
            
            # Re-retrieval needed
            if result.retry_query and attempt < self.max_retries:
                logger.info(f"Retry {attempt + 1}/{self.max_retries}: {result.retry_query}")
                current_query = result.retry_query
                chunks = retrieval_fn(current_query)
                
                # Recompute embedding for new query
                if self.embedding_model is not None:
                    query_embedding = self.embedding_model.encode(
                        current_query,
                        normalize_embeddings=True
                    )
        
        # Final attempt failed
        return result, self.max_retries
    
    def _extract_keywords(self, text: str) -> set:
        """Extract meaningful keywords from text."""
        import re
        
        # Simple keyword extraction: lowercase, remove stopwords
        stopwords = {
            "a", "an", "the", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "can", "to", "of",
            "in", "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below", "up",
            "down", "out", "off", "over", "under", "again", "further",
            "then", "once", "here", "there", "when", "where", "why", "how",
            "all", "each", "few", "more", "most", "other", "some", "such",
            "no", "nor", "not", "only", "own", "same", "so", "than", "too",
            "very", "just", "and", "but", "if", "or", "because", "until",
            "while", "what", "which", "who", "whom", "this", "that", "these",
            "those", "am", "it", "its", "about", "also", "i", "me", "my",
            "myself", "we", "our", "ours", "you", "your", "he", "him", "his",
            "she", "her", "they", "them", "their"
        }
        
        words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
        keywords = {w for w in words if w not in stopwords}
        
        return keywords
    
    def _compute_keyword_overlap(self, query_keywords: set, chunk_text: str) -> float:
        """Compute fraction of query keywords found in chunk."""
        if not query_keywords:
            return 0.5  # Neutral score if no keywords
        
        chunk_keywords = self._extract_keywords(chunk_text)
        overlap = query_keywords & chunk_keywords
        
        return len(overlap) / len(query_keywords)
    
    def _generate_retry_query(self, original_query: str, rejected_chunks: List[dict]) -> str:
        """
        Generate a modified query for re-retrieval.
        
        Strategies:
        1. Add specificity from rejected chunk topics
        2. Rephrase to be more explicit
        """
        # Simple strategy: make query more explicit
        if "?" not in original_query:
            return f"What is {original_query}?"
        
        # Try to expand abbreviations or add context
        return f"detailed information about {original_query}"


class LLMValidator:
    """
    Optional LLM-based validation for edge cases.
    
    Uses the generation LLM to verify chunk relevance.
    More accurate but slower than embedding-based validation.
    """
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        
    def validate_chunk(self, query: str, chunk_text: str) -> Tuple[bool, float]:
        """
        Use LLM to validate if chunk is relevant to query.
        
        Returns:
            Tuple of (is_relevant, confidence_score)
        """
        if self.llm_client is None:
            return True, 0.5  # Default to accepting
        
        prompt = f"""Determine if the following text chunk is relevant to answering the query.

Query: {query}

Chunk:
{chunk_text[:500]}...

Respond with only:
RELEVANT: <confidence 0-100>
or
NOT_RELEVANT: <confidence 0-100>
"""
        
        try:
            response = self.llm_client.generate_content(prompt)
            text = response.text.strip().upper()
            
            if text.startswith("RELEVANT"):
                confidence = self._extract_confidence(text)
                return True, confidence / 100
            else:
                confidence = self._extract_confidence(text)
                return False, confidence / 100
                
        except Exception as e:
            logger.warning(f"LLM validation failed: {e}")
            return True, 0.5  # Default to accepting
    
    @staticmethod
    def _extract_confidence(text: str) -> float:
        """Extract confidence number from response."""
        import re
        match = re.search(r'(\d+)', text)
        if match:
            return min(100, max(0, int(match.group(1))))
        return 50
