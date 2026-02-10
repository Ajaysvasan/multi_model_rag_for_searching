"""
Answer Generation Layer with Citations.

Uses local GGUF model via llama-cpp-python for inference.
Falls back to HuggingFace API if USE_LOCAL_MODEL is False.
"""

import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from config import Config
from .prompts import SYSTEM_PROMPTS, format_context_for_generation

logger = logging.getLogger("generation")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


@dataclass
class Citation:
    """Represents a citation to a source chunk."""
    citation_id: int
    chunk_id: str
    source_path: str
    chunk_text: str
    start_offset: int
    end_offset: int
    relevance_score: float = 0.0


@dataclass
class GenerationResult:
    """Result of answer generation."""
    answer: str
    citations: List[Citation] = field(default_factory=list)
    raw_response: str = ""
    model_used: str = ""
    tokens_used: int = 0
    success: bool = True
    error: Optional[str] = None


class LlamaGenerator:
    """
    Generates answers using local GGUF model (llama-cpp-python) or HuggingFace API.
    """
    
    DEFAULT_MODEL = "TheBloke/Mistral-7B-Instruct-v0.2-GGUF"
    API_URL = "https://api-inference.huggingface.co/models"
    
    def __init__(
        self,
        model_name: str = None,
        models_dir: str = None,
        use_local: bool = None,
        api_token: str = None,
    ):
        self.model_name = model_name or getattr(Config, 'GENERATION_MODEL', self.DEFAULT_MODEL)
        self.model_file = getattr(Config, 'GENERATION_MODEL_FILE', 'mistral-7b-instruct-v0.2.Q4_K_M.gguf')
        self.models_dir = Path(models_dir or getattr(Config, 'MODELS_DIR', 'models'))
        self.use_local = use_local if use_local is not None else getattr(Config, 'USE_LOCAL_MODEL', True)
        self.api_token = api_token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
        
        self.model = None
        self._is_loaded = False
    
    def _get_model_path(self) -> Path:
        """Get the local path to the GGUF model file."""
        return self.models_dir / self.model_file
    
    def is_model_cached(self) -> bool:
        """Check if model file exists locally."""
        if not self.use_local:
            return True
        return self._get_model_path().exists()
    
    def load_model(self, show_progress: bool = True):
        """Load the model."""
        if self._is_loaded:
            return
        
        if not self.use_local:
            if show_progress:
                logger.info(f"Using HuggingFace API: {self.model_name}")
            self._is_loaded = True
            return
        
        # Local GGUF model mode
        from llama_cpp import Llama
        
        model_path = self._get_model_path()
        
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model not found at {model_path}. "
                f"Run 'python download_model.py' first."
            )
        
        if show_progress:
            logger.info(f"Loading GGUF model: {model_path}")
        
        # Detect GPU layers
        n_gpu_layers = 0
        try:
            import torch
            if torch.cuda.is_available():
                n_gpu_layers = -1  # Offload all layers to GPU
                if show_progress:
                    logger.info(f"GPU detected: {torch.cuda.get_device_name(0)}")
        except ImportError:
            pass
        
        self.model = Llama(
            model_path=str(model_path),
            n_ctx=8192,         # Larger context window
            n_gpu_layers=n_gpu_layers,
            n_batch=512,        # Faster prompt processing
            verbose=False,
        )
        
        if show_progress:
            logger.info("Model loaded successfully")
        self._is_loaded = True
    
    def _call_api(self, messages: List[dict], max_new_tokens: int = 256, temperature: float = 0.7) -> str:
        """Call HuggingFace Inference API."""
        import requests
        
        url = f"{self.API_URL}/{self.model_name}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_new_tokens,
            "temperature": temperature,
            "stream": False,
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        if response.status_code != 200:
            raise Exception(f"API error ({response.status_code}): {response.text}")
        
        result = response.json()
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
        raise Exception(f"Unexpected API response: {result}")
    
    def _generate_local(self, messages: List[dict], max_new_tokens: int = 256, temperature: float = 0.7) -> str:
        """Generate using local GGUF model via llama-cpp-python."""
        response = self.model.create_chat_completion(
            messages=messages,
            max_tokens=max_new_tokens,
            temperature=temperature,
            top_p=0.9,
        )
        
        return response["choices"][0]["message"]["content"]
    
    @staticmethod
    def _clean_response(text: str) -> str:
        """Post-process to remove hallucinated references/URLs."""
        # Remove any "References:" or "Sources:" sections the model generates
        for marker in ["References:", "Sources:", "Bibliography:", "Works Cited:"]:
            idx = text.find(marker)
            if idx > 0:
                text = text[:idx].rstrip()
        
        # Remove hallucinated URLs
        text = re.sub(r'https?://\S+', '[link removed]', text)
        
        # Remove hallucinated "Retrieved from" citations
        text = re.sub(r'Retrieved (?:from|on) .+?(?:\n|$)', '', text)
        
        return text.strip()
    
    def generate(
        self,
        query: str,
        chunks: List[dict],
        include_sources: bool = True,
        max_new_tokens: int = 256,
        temperature: float = 0.7,
    ) -> GenerationResult:
        """Generate answer from retrieved chunks."""
        if not chunks:
            return GenerationResult(
                answer="I couldn't find any relevant information.",
                success=True,
                model_used=self.model_name,
            )
        
        if not self._is_loaded:
            self.load_model(show_progress=False)
        
        # Limit to top 3 chunks for speed, skip empty ones
        valid_chunks = [c for c in chunks if c.get("chunk_text", "").strip()]
        if not valid_chunks:
            return GenerationResult(
                answer="The retrieved documents could not be read. Please try re-ingesting the data.",
                success=False,
                error="All chunks have empty text",
                model_used=self.model_name,
            )
        
        context = format_context_for_generation(
            valid_chunks, include_source=include_sources, max_chunks=3
        )
        
        system_message = """You are a helpful assistant that answers questions based on provided context.
RULES:
1. ONLY use information from the provided context
2. Cite sources using [1], [2], etc.
3. If context is insufficient, say so clearly
4. Be concise but thorough
5. NEVER invent URLs, links, or references not in the context
6. Do NOT add a References or Sources section"""

        user_message = f"""CONTEXT:
{context}

QUESTION: {query}

Answer using ONLY the context above, with inline citations:"""
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]
        
        try:
            if self.use_local:
                raw_text = self._generate_local(messages, max_new_tokens, temperature)
            else:
                raw_text = self._call_api(messages, max_new_tokens, temperature)
            
            # Post-process to remove hallucinations
            cleaned_text = self._clean_response(raw_text)
            
            citations = []
            for i, chunk in enumerate(valid_chunks[:3]):
                citations.append(Citation(
                    citation_id=i + 1,
                    chunk_id=chunk.get("chunk_id", f"chunk_{i}"),
                    source_path=chunk.get("source_path", "unknown"),
                    chunk_text=chunk.get("chunk_text", "")[:200],
                    start_offset=chunk.get("start_offset", 0),
                    end_offset=chunk.get("end_offset", 0),
                    relevance_score=chunk.get("score", 0.0),
                ))
            
            return GenerationResult(
                answer=cleaned_text,
                citations=citations,
                raw_response=raw_text,
                model_used=self.model_name,
                success=True,
            )
            
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return GenerationResult(
                answer=f"Error: {str(e)}",
                success=False,
                error=str(e),
                model_used=self.model_name,
            )


AnswerGenerator = LlamaGenerator
