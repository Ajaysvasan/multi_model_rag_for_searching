import logging
import os
import re
import struct
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from platform import system
from typing import List, Optional

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from config import Config

from .prompts import (
    SYSTEM_PROMPT,
    estimate_tokens,
    format_context_for_generation,
    wrap_prompt,
)



logger = logging.getLogger("generation")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def _context_budget(n_ctx: int, fixed_text: str, max_new_tokens: int) -> int:
    """Tokens left for retrieved passages after everything else is accounted for.

    Nothing computed this before: five passages were concatenated regardless of
    n_ctx, so a run of large chunks produced a prompt longer than the context
    window and llama.cpp raised instead of answering.
    """
    margin = int(getattr(Config, "CTX_SAFETY_MARGIN", 192))
    budget = n_ctx - estimate_tokens(fixed_text) - max_new_tokens - margin
    return max(budget, 256)


@dataclass
class Citation:

    citation_id: int
    chunk_id: str
    source_path: str
    chunk_text: str
    start_offset: int
    end_offset: int
    relevance_score: float = 0.0


@dataclass
class GenerationResult:

    answer: str
    citations: List[Citation] = field(default_factory=list)
    raw_response: str = ""
    model_used: str = ""
    tokens_used: int = 0
    success: bool = True
    error: Optional[str] = None


class LlamaGenerator:

    DEFAULT_MODEL = Config.DEFAULT_MODEL
    API_URL = "https://router.huggingface.co/models"

    def __init__(
        self,
        model_name: str = "",
        models_dir: str = "",
        use_local: bool = None,
        api_token: str = "",
    ):
        self.model_name = model_name or getattr(
            Config, "GENERATION_MODEL", self.DEFAULT_MODEL
        )
        self.model_file = getattr(
            Config, "GENERATION_MODEL_FILE", "mistral-7b-instruct-v0.2.Q4_K_M.gguf"
        )
        self.models_dir = Path(models_dir or getattr(Config, "MODELS_DIR", "models"))
        self.use_local = (
            use_local
            if use_local is not None
            else getattr(Config, "USE_LOCAL_MODEL", True)
        )
        self.api_token = (
            api_token
            or os.environ.get("HF_TOKEN")
            or os.environ.get("HUGGINGFACE_TOKEN")
        )

        self.model = None
        self._is_loaded = False

    def _get_model_path(self) -> Path:
        return self.models_dir / self.model_file

    def is_model_cached(self) -> bool:
        if not self.use_local:
            return True
        return self._get_model_path().exists()

    def load_model(self, show_progress: bool = True):
        if self._is_loaded:
            return

        # Enforce offline mode if configured
        if getattr(Config, "OFFLINE_MODE", False):
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            if not self.use_local:
                logger.warning(
                    "Offline mode enabled but use_local is False. Forcing use_local=True."
                )
                self.use_local = True

        if not self.use_local:
            if show_progress:
                logger.info(f"Using HuggingFace API: {self.model_name}")
            self._is_loaded = True
            return

        from llama_cpp import Llama

        model_path = self._get_model_path()

        if not model_path.exists():
            raise FileNotFoundError(
                f"Model not found at {model_path}. "
                f"Run 'python download_model.py' first."
            )

        if show_progress:
            logger.info(f"Loading GGUF model: {model_path}")

        # Ask llama.cpp itself, not torch. torch.cuda.is_available() only says
        # the machine has a GPU -- it says nothing about whether THIS llama.cpp
        # build has a GPU backend compiled in. The old code set n_gpu_layers=-1
        # on a CPU-only wheel, which llama.cpp silently ignores, so the logs
        # claimed GPU acceleration that was never happening.
        n_gpu_layers = int(getattr(Config, "N_GPU_LAYERS", -1))
        gpu_capable = False
        try:
            import llama_cpp

            gpu_capable = bool(llama_cpp.llama_supports_gpu_offload())
        except Exception as e:  # pragma: no cover - depends on the wheel
            logger.debug(f"Could not query GPU offload support: {e}")

        if n_gpu_layers != 0 and not gpu_capable:
            logger.warning(
                "Config.N_GPU_LAYERS=%s requests GPU offload, but this "
                "llama-cpp-python build has no GPU backend "
                "(llama_supports_gpu_offload() is False). Running on CPU. "
                "Rebuild with CMAKE_ARGS=\"-DGGML_CUDA=on\" to use the GPU.",
                n_gpu_layers,
            )
            n_gpu_layers = 0
        elif n_gpu_layers != 0:
            logger.info(f"GPU offload enabled (n_gpu_layers={n_gpu_layers})")

        n_threads = int(getattr(Config, "N_THREADS", 0) or 0) or os.cpu_count() or 4
        self.n_ctx = int(getattr(Config, "N_CTX", 4096))

        self.model = Llama(
            model_path=str(model_path),
            n_ctx=self.n_ctx,
            n_gpu_layers=n_gpu_layers,
            n_batch=int(getattr(Config, "N_BATCH", 512)),
            n_threads=n_threads,
            verbose=False,
        )

        if show_progress:
            logger.info(
                f"Model loaded (n_ctx={self.n_ctx}, n_batch="
                f"{getattr(Config, 'N_BATCH', 512)}, n_threads={n_threads}, "
                f"gpu_layers={n_gpu_layers})"
            )
        self._is_loaded = True

    def _call_api(
        self, messages: List[dict], max_new_tokens: int = 200, temperature: float = 0.1
    ) -> str:
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

    def _generate_local(
        self, messages: List[dict], max_new_tokens: int = 200, temperature: float = 0.1
    ) -> str:
        response = self.model.create_chat_completion(
            messages=messages,
            max_tokens=max_new_tokens,
            temperature=temperature,
            top_p=0.9,
            top_k=20,
            repeat_penalty=1.1,
        )

        return response["choices"][0]["message"]["content"]

    _REFUSAL_PHRASES = [
        "couldn't find",
        "could not find",
        "do not contain enough",
        "don't contain enough",
        "no relevant information",
        "not contain enough information",
        "cannot answer",
        "unable to find",
        "no information available",
        "not enough information",
        # Models routinely refuse in wording the list above missed, and an
        # undetected refusal keeps its citations -- so a "none of these passages
        # mention X" answer was shipping 4 bogus sources to the UI.
        "none of the provided",
        "none of the passages",
        "none of the context",
        "do not mention",
        "does not mention",
        "doesn't mention",
        "not mentioned in",
        "cannot provide an answer",
        "no mention of",
    ]

    # Models phrase refusals in endless variants ("I'm unable to answer ... as
    # it does not contain any relevant information"), and an undetected refusal
    # keeps its citations -- which is how a non-answer ends up showing the user
    # four fabricated sources. Match the shape instead of enumerating wordings.
    _REFUSAL_RE = re.compile(
        r"\b(?:do(?:es)?\s+not|don'?t|doesn'?t|cannot|can'?t|could\s+not|"
        r"couldn'?t|unable\s+to|no|none\s+of)\b[^.]{0,60}?\b"
        r"(?:answer|contain|mention|find|provide|relevant|information)\b",
        re.IGNORECASE,
    )

    @staticmethod
    def _is_refusal(text: str) -> bool:
        # Only the FIRST SENTENCE counts, for both checks. A real answer may say
        # "the passages do not mention ultrasound, but describe MRI [2]" in its
        # second sentence -- that is an answer. Refusals lead with the refusal.
        first = re.split(r"(?<=[.!?])\s", text.lower().strip(), maxsplit=1)[0]
        if any(p in first for p in LlamaGenerator._REFUSAL_PHRASES):
            return True
        return bool(LlamaGenerator._REFUSAL_RE.search(first))

    @staticmethod
    def _extract_cited_indices(text: str) -> set:
        """Extract citation indices [1], [2], etc. from generated text.

        Returns a set of integers representing which source passages the
        model actually referenced in its answer.  This is used to filter
        the citation list so that only *truly cited* chunks are returned,
        which dramatically improves citation precision.
        """
        matches = re.findall(r'\[(\d+)\]', text)
        return {int(m) for m in matches}

    @staticmethod
    def _clean_response(text: str) -> str:
        """Post-process to remove hallucinated references/URLs."""
        for marker in [
            "References:",
            "Sources:",
            "Bibliography:",
            "Works Cited:",
            "Citation:",
            "Citations:",
            "Further Reading:",
        ]:
            idx = text.find(marker)
            if idx > 0:
                text = text[:idx].rstrip()

        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"Retrieved (?:from|on) .+?(?:\n|$)", "", text)
        text = re.sub(r"\([a-zA-Z\s,&]+,?\s*(?:n\.d\.|\d{4})\)", "", text)
        text = re.sub(r"(?i)reportlab[\w\s]*(?:generated|pdf)?[^.]*\.?", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"  +", " ", text)

        return text.strip()

    def generate(
        self,
        query: str,
        chunks: List[dict],
        include_sources: bool = True,
        max_new_tokens: int = Config.MAX_NEW_TOKENS,
        temperature: float = Config.GEN_TEMPERATURE,
        conversation_context: List[dict] = None,
    ) -> GenerationResult:
        if not chunks:
            return GenerationResult(
                answer="I couldn't find any relevant information.",
                success=True,
                model_used=self.model_name,
            )

        if not self._is_loaded:
            self.load_model(show_progress=False)

        valid_chunks = [c for c in chunks if c.get("chunk_text", "").strip()]
        if not valid_chunks:
            return GenerationResult(
                answer="The retrieved documents could not be read. Please try re-ingesting the data.",
                success=False,
                error="All chunks have empty text",
                model_used=self.model_name,
            )

        # Chunks under 50 chars are likely just metadata/headers — return raw
        if all(len(c.get("chunk_text", "").strip()) < 50 for c in valid_chunks):
            bullets = "\n".join(
                f"• {c.get('chunk_text', '').strip()}" for c in valid_chunks
            )
            return GenerationResult(
                answer=f"The retrieved content is very brief:\n{bullets}",
                success=True,
                model_used=self.model_name,
            )

        system_message = SYSTEM_PROMPT

        # Budget the passages against the real context window rather than
        # assuming five always fit.
        history_preview = ""
        if conversation_context:
            history_preview = " ".join(
                str(t.get("content", ""))[:150] for t in conversation_context[-2:]
            )
        budget = _context_budget(
            n_ctx=getattr(self, "n_ctx", None) or int(getattr(Config, "N_CTX", 4096)),
            fixed_text=system_message + query + history_preview,
            max_new_tokens=max_new_tokens,
        )

        context = format_context_for_generation(
            valid_chunks,
            include_source=include_sources,
            max_chunks=int(getattr(Config, "MAX_CONTEXT_CHUNKS", 5)),
            token_budget=budget,
            char_limit=int(getattr(Config, "CHUNK_CHAR_LIMIT", 1200)),
        )

        user_message = f"""CONTEXT:
{context}

QUESTION: {query}

Answer the question using ONLY the context above. You MUST cite every relevant passage with inline [1], [2], etc. citations. Every claim needs a citation:"""

        if conversation_context:
            history_lines = []
            for turn in conversation_context[-2:]:
                role = turn.get("role", "user").capitalize()
                content = turn.get("content", "")[:150]
                history_lines.append(f"{role}: {content}")
            history_str = "\n".join(history_lines)
            user_message = f"CONVERSATION HISTORY:\n{history_str}\n\n{user_message}"

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]

        try:
            if self.use_local:
                raw_text = self._generate_local(messages, max_new_tokens, temperature)
            else:
                raw_text = self._call_api(messages, max_new_tokens, temperature)

            cleaned_text = self._clean_response(raw_text)

            # If the LLM refused to answer, return with no citations
            if self._is_refusal(cleaned_text):
                return GenerationResult(
                    answer=cleaned_text,
                    citations=[],
                    raw_response=raw_text,
                    model_used=self.model_name,
                    success=True,
                )

            # Only include citations for chunks the model actually referenced
            cited_indices = self._extract_cited_indices(cleaned_text)

            citations = []
            for i, chunk in enumerate(valid_chunks[:5]):
                citation_id = i + 1
                # If the model cited specific sources, only include those;
                # if it cited nothing (edge case), include all as fallback.
                if cited_indices and citation_id not in cited_indices:
                    continue
                citations.append(
                    Citation(
                        citation_id=citation_id,
                        chunk_id=chunk.get("chunk_id", f"chunk_{i}"),
                        source_path=chunk.get("source_path", "unknown"),
                        chunk_text=chunk.get("chunk_text", "")[:200],
                        start_offset=chunk.get("start_offset", 0),
                        end_offset=chunk.get("end_offset", 0),
                        relevance_score=chunk.get("score", 0.0),
                    )
                )

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

    def __del__(self):
        if self.model is not None:
            del self.model


class MmapGenerator:
    """
    Delegates LLM inference to the C++ llm_backend binary which loads the
    GGUF model via mmap (VAS), keeping RSS low while the OS pages in weights
    on demand.  IPC uses a length-prefixed binary protocol over stdin/stdout.
    """

    DEFAULT_MODEL = Config.DEFAULT_MODEL

    def __init__(
        self,
        model_path: str = "",
        model_name: str = "",
        backend_path: str = "",
    ):
        base_dir = Path(__file__).resolve().parent.parent
        model_file = getattr(
            Config,
            "GENERATION_MODEL_FILE",
            "mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        )

        # backend binary — resolve relative paths against backend/
        bp = Path(backend_path) if backend_path else base_dir / "bin" / "llm_backend"
        self.backend_path = bp if bp.is_absolute() else base_dir / bp

        # model_path can be a directory OR a full file path
        if model_path:
            mp = Path(model_path)
            if not mp.is_absolute():
                mp = base_dir / mp
            if mp.is_dir() or not mp.suffix:  # directory → append model filename
                mp = mp / model_file
        else:
            models_dir = Path(getattr(Config, "MODELS_DIR", "models"))
            if not models_dir.is_absolute():
                models_dir = base_dir / models_dir
            mp = models_dir / model_file
        self.model_path = mp

        self.model_name = model_name or getattr(
            Config, "GENERATION_MODEL", self.DEFAULT_MODEL
        )

        lib_dir = str(base_dir / "third_party" / "llama.cpp" / "build" / "bin")
        current_ld = os.environ.get("LD_LIBRARY_PATH", "")
        if lib_dir not in current_ld:
            os.environ["LD_LIBRARY_PATH"] = f"{lib_dir}:{current_ld}"

        self._proc: Optional[subprocess.Popen] = None
        self._is_loaded = False

    def _ensure_backend(self):
        """Lazily spawn the C++ backend; reuse across calls, restart if dead."""
        if self._is_loaded and self._proc and self._proc.poll() is None:
            return

        if not self.backend_path.exists():
            raise FileNotFoundError(
                f"C++ backend not found at {self.backend_path}. "
                "Compile it first (see llm_backend/main.cpp)."
            )
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model not found at {self.model_path}. "
                "Run 'python download_model.py' first."
            )

        logger.info(f"Spawning C++ mmap backend: {self.backend_path} {self.model_path}")

        self._proc = subprocess.Popen(
            [str(self.backend_path), str(self.model_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )

        line = self._proc.stdout.readline().decode("utf-8").strip()
        if line != "READY":
            stderr_out = ""
            try:
                stderr_out = self._proc.stderr.read(2048).decode(
                    "utf-8", errors="replace"
                )
            except Exception:
                pass
            raise RuntimeError(
                f"C++ backend failed to start. Got: '{line}'. stderr: {stderr_out}"
            )

        logger.info("C++ mmap backend is READY")
        self._is_loaded = True

    def load_model(self, show_progress: bool = True):
        self._ensure_backend()

    def is_model_cached(self) -> bool:
        return self.model_path.exists()

    # ---- IPC: 4-byte LE uint32 length prefix + UTF-8 payload ----

    def _write_msg(self, s: str):
        data = s.encode("utf-8")
        self._proc.stdin.write(struct.pack("<I", len(data)))
        self._proc.stdin.write(data)
        self._proc.stdin.flush()

    def _read_msg(self) -> str:
        hdr = self._proc.stdout.read(4)
        if not hdr:
            raise RuntimeError("C++ backend closed unexpectedly")
        (n,) = struct.unpack("<I", hdr)
        data = self._proc.stdout.read(n)
        return data.decode("utf-8", errors="replace")

    def _generate_via_backend(self, prompt: str) -> str:
        self._ensure_backend()
        self._write_msg(prompt)
        response = self._read_msg()
        if response.startswith("ERROR:"):
            raise RuntimeError(f"C++ backend error: {response}")
        return response

    def generate(
        self,
        query: str,
        chunks: List[dict],
        include_sources: bool = True,
        max_new_tokens: int = Config.MAX_NEW_TOKENS,
        temperature: float = Config.GEN_TEMPERATURE,
        conversation_context: List[dict] = None,
    ) -> GenerationResult:

        if not chunks:
            return GenerationResult(
                answer="I couldn't find any relevant information.",
                success=True,
                model_used=self.model_name,
            )

        valid_chunks = [c for c in chunks if c.get("chunk_text", "").strip()]
        if not valid_chunks:
            return GenerationResult(
                answer="The retrieved documents could not be read. "
                "Please try re-ingesting the data.",
                success=False,
                error="All chunks have empty text",
                model_used=self.model_name,
            )

        # Chunks under 50 chars are likely just metadata/headers — return raw
        if all(len(c.get("chunk_text", "").strip()) < 50 for c in valid_chunks):
            bullets = "\n".join(
                f"• {c.get('chunk_text', '').strip()}" for c in valid_chunks
            )
            return GenerationResult(
                answer=f"The retrieved content is very brief:\n{bullets}",
                success=True,
                model_used=self.model_name,
            )

        system_message = SYSTEM_PROMPT

        history_preview = ""
        if conversation_context:
            history_preview = " ".join(
                str(t.get("content", ""))[:150] for t in conversation_context[-2:]
            )
        budget = _context_budget(
            n_ctx=int(getattr(Config, "N_CTX", 4096)),
            fixed_text=system_message + query + history_preview,
            max_new_tokens=max_new_tokens,
        )

        context = format_context_for_generation(
            valid_chunks,
            include_source=include_sources,
            max_chunks=int(getattr(Config, "MAX_CONTEXT_CHUNKS", 5)),
            token_budget=budget,
            char_limit=int(getattr(Config, "CHUNK_CHAR_LIMIT", 1200)),
        )

        user_message = (
            f"CONTEXT:\n{context}\n\n"
            f"QUESTION: {query}\n\n"
            "Answer the question using ONLY the context above. You MUST cite every relevant passage with inline [1], [2], etc. citations. Every claim needs a citation:"
        )

        if conversation_context:
            history_lines = []
            for turn in conversation_context[-2:]:
                role = turn.get("role", "user").capitalize()
                content = turn.get("content", "")[:150]
                history_lines.append(f"{role}: {content}")
            history_str = "\n".join(history_lines)
            user_message = f"CONVERSATION HISTORY:\n{history_str}\n\n{user_message}"

        # The C++ backend has no chat template, so wrap here. This used to be
        # hardcoded to Mistral's [INST] <<SYS>> form, which produces garbage for
        # any other model -- including the StableLM-Zephyr default.
        prompt = wrap_prompt(system_message, user_message)

        try:
            raw_text = self._generate_via_backend(prompt)
            cleaned_text = LlamaGenerator._clean_response(raw_text)

            if LlamaGenerator._is_refusal(cleaned_text):
                return GenerationResult(
                    answer=cleaned_text,
                    citations=[],
                    raw_response=raw_text,
                    model_used=self.model_name,
                    success=True,
                )

            # Only include citations for chunks the model actually referenced
            cited_indices = LlamaGenerator._extract_cited_indices(cleaned_text)

            citations = []
            for i, chunk in enumerate(valid_chunks[:5]):
                citation_id = i + 1
                if cited_indices and citation_id not in cited_indices:
                    continue
                citations.append(
                    Citation(
                        citation_id=citation_id,
                        chunk_id=chunk.get("chunk_id", f"chunk_{i}"),
                        source_path=chunk.get("source_path", "unknown"),
                        chunk_text=chunk.get("chunk_text", "")[:200],
                        start_offset=chunk.get("start_offset", 0),
                        end_offset=chunk.get("end_offset", 0),
                        relevance_score=chunk.get("score", 0.0),
                    )
                )

            return GenerationResult(
                answer=cleaned_text,
                citations=citations,
                raw_response=raw_text,
                model_used=self.model_name,
                success=True,
            )

        except Exception as e:
            logger.error(f"MmapGenerator generation failed: {e}")
            return GenerationResult(
                answer=f"Error: {str(e)}",
                success=False,
                error=str(e),
                model_used=self.model_name,
            )

    def close(self):
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
            self._is_loaded = False
            logger.info("C++ mmap backend terminated")

    def __del__(self):
        self.close()


AnswerGenerator = None
if system().lower() in ["linux", "darwin"]:
    AnswerGenerator = MmapGenerator
else:
    AnswerGenerator = LlamaGenerator
