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

from .prompts import format_context_for_generation

logger = logging.getLogger("generation")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


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

        n_gpu_layers = 0
        try:
            import torch

            if torch.cuda.is_available():
                n_gpu_layers = -1
                if show_progress:
                    logger.info(f"GPU detected: {torch.cuda.get_device_name(0)}")
        except ImportError:
            pass

        n_threads = os.cpu_count() or 4

        self.model = Llama(
            model_path=str(model_path),
            n_ctx=2048,
            n_gpu_layers=n_gpu_layers,
            n_batch=256,
            n_threads=n_threads,
            verbose=False,
        )

        if show_progress:
            logger.info("Model loaded successfully")
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
    ]

    @staticmethod
    def _is_refusal(text: str) -> bool:
        lower = text.lower()
        return any(p in lower for p in LlamaGenerator._REFUSAL_PHRASES)

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
        max_new_tokens: int = 128,
        temperature: float = 0.1,
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

        context = format_context_for_generation(
            valid_chunks, include_source=include_sources, max_chunks=5
        )

        system_message = """You are a factual Q&A assistant. Answer ONLY from the provided context.
STRICT RULES:
1. Use ONLY facts stated in the context below — nothing else.
2. Cite sources inline as [1], [2], etc.
3. If the context lacks sufficient information, say ONLY: "I could not find relevant information in the available sources." Do NOT cite any source numbers or file names.
4. Be concise. Do NOT pad your answer.
5. NEVER invent or guess URLs, links, dates, statistics, or references.
6. NEVER mention PDF metadata, file formats, ReportLab, or how documents were created.
7. Do NOT add References, Sources, Bibliography, or Citation sections.
8. Do NOT generate content beyond what the context provides.
9. If NONE of the context passages relate to the question, do NOT cite any sources — respond only with the refusal message from rule 3."""

        user_message = f"""CONTEXT:
{context}

QUESTION: {query}

Answer the question using ONLY the context above. Use inline [1], [2] citations:"""

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
                    answer=cleaned_text, citations=[],
                    raw_response=raw_text, model_used=self.model_name,
                    success=True,
                )

            citations = []
            for i, chunk in enumerate(valid_chunks[:5]):
                citations.append(
                    Citation(
                        citation_id=i + 1,
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
        max_new_tokens: int = 200,
        temperature: float = 0.6,
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

        context = format_context_for_generation(
            valid_chunks, include_source=include_sources, max_chunks=5
        )

        system_message = (
            "You are a factual Q&A assistant. Answer ONLY from the provided context.\n"
            "STRICT RULES:\n"
            "1. Use ONLY facts stated in the context below — nothing else.\n"
            "2. Cite sources inline as [1], [2], etc.\n"
            "3. If the context lacks sufficient information, say ONLY: "
            '"I could not find relevant information in the available sources." '
            "Do NOT cite any source numbers or file names.\n"
            "4. Be concise. Do NOT pad your answer.\n"
            "5. NEVER invent or guess URLs, links, dates, statistics, or references.\n"
            "6. NEVER mention PDF metadata, file formats, ReportLab, or how documents were created.\n"
            "7. Do NOT add References, Sources, Bibliography, or Citation sections.\n"
            "8. Do NOT generate content beyond what the context provides.\n"
            "9. If NONE of the context passages relate to the question, do NOT cite any sources — "
            "respond only with the refusal message from rule 3."
        )

        user_message = (
            f"CONTEXT:\n{context}\n\n"
            f"QUESTION: {query}\n\n"
            "Answer the question using ONLY the context above. Use inline [1], [2] citations:"
        )

        if conversation_context:
            history_lines = []
            for turn in conversation_context[-2:]:
                role = turn.get("role", "user").capitalize()
                content = turn.get("content", "")[:150]
                history_lines.append(f"{role}: {content}")
            history_str = "\n".join(history_lines)
            user_message = f"CONVERSATION HISTORY:\n{history_str}\n\n{user_message}"

        # Wrap in Mistral [INST] tags — the C++ backend has no chat template
        prompt = f"[INST] <<SYS>>\n{system_message}\n<</SYS>>\n\n{user_message} [/INST]"

        try:
            raw_text = self._generate_via_backend(prompt)
            cleaned_text = LlamaGenerator._clean_response(raw_text)

            if LlamaGenerator._is_refusal(cleaned_text):
                return GenerationResult(
                    answer=cleaned_text, citations=[],
                    raw_response=raw_text, model_used=self.model_name,
                    success=True,
                )

            citations = []
            for i, chunk in enumerate(valid_chunks[:5]):
                citations.append(
                    Citation(
                        citation_id=i + 1,
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
