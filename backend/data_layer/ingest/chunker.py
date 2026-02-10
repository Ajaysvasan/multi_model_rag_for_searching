import hashlib
import re
from dataclasses import dataclass
from typing import List, Tuple

CHUNK_VERSION = "chunk_v1"
TOKENS_PER_WORD: float = 0.75


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    text: str
    start_char: int
    end_char: int
    paragraph_start: int
    paragraph_end: int
    chunk_index: int
    chunk_version: str


class TextChunker:
    def __init__(
        self,
        target_tokens: int = 400,
        max_tokens: int = 600,
        overlap_tokens: int = 80,
        chunk_version: str = CHUNK_VERSION,
    ):
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.chunk_version = chunk_version

    def chunk(
        self,
        text: str,
        document_id: str,
        normalization_version: str,
    ) -> List[Chunk]:

        paragraphs = split_paragraphs(text)
        chunks: List[Chunk] = []

        current_paras = []
        current_tokens = 0
        chunk_index = 0
        para_index = 0

        i = 0
        while i < len(paragraphs):
            para_text, start, end = paragraphs[i]
            tokens = estimate_tokens(para_text)

            # If a single paragraph is too large, force split by sentences
            if tokens > self.max_tokens:
                # Split paragraph into sentences with proper offset tracking
                sentence_pattern = re.compile(r"(?<=[.!?])\s+")
                sentences = sentence_pattern.split(para_text)

                # Track position within the paragraph
                sent_cursor = 0
                for sent in sentences:
                    if not sent.strip():
                        sent_cursor += len(sent)
                        continue

                    # Find the actual position of this sentence in para_text
                    sent_start_in_para = para_text.find(sent, sent_cursor)
                    if sent_start_in_para == -1:
                        sent_start_in_para = sent_cursor

                    sent_end_in_para = sent_start_in_para + len(sent)

                    # Calculate absolute offsets (paragraph start + sentence offset)
                    abs_start = start + sent_start_in_para
                    abs_end = start + sent_end_in_para

                    chunks.append(
                        self._emit_chunk(
                            [(sent, abs_start, abs_end)],
                            document_id,
                            normalization_version,
                            abs_start,
                            abs_end,
                            para_index,
                            para_index,
                            chunk_index,
                        )
                    )
                    chunk_index += 1
                    sent_cursor = sent_end_in_para

                i += 1
                para_index += 1
                continue

            # Check if adding this paragraph fits in target
            if current_tokens + tokens <= self.target_tokens:
                current_paras.append((para_text, start, end))
                current_tokens += tokens
                i += 1
                para_index += 1
            else:
                if not current_paras:
                    current_paras.append((para_text, start, end))
                    current_tokens += tokens
                    i += 1
                    para_index += 1
                    continue
                chunks.append(
                    self._emit_chunk(
                        current_paras,
                        document_id,
                        normalization_version,
                        current_paras[0][1],
                        current_paras[-1][2],
                        para_index - len(current_paras),
                        para_index - 1,
                        chunk_index,
                    )
                )
                chunk_index += 1

                # Overlap handling
                current_paras, current_tokens = self._apply_overlap(current_paras)

                # We do NOT increment 'i' here because we still need to process
                # the current paragraph (paragraphs[i]) in the next iteration
                # (now that the buffer is cleared/overlapped).

        # Flush any remaining paragraphs
        if current_paras:
            chunks.append(
                self._emit_chunk(
                    current_paras,
                    document_id,
                    normalization_version,
                    current_paras[0][1],
                    current_paras[-1][2],
                    para_index - len(current_paras),
                    para_index - 1,
                    chunk_index,
                )
            )

        return chunks

    def _apply_overlap(self, paras):
        overlap = []
        tokens = 0

        for para in reversed(paras):
            para_tokens = estimate_tokens(para[0])
            if tokens + para_tokens > self.overlap_tokens:
                break
            overlap.insert(0, para)
            tokens += para_tokens

        return overlap, tokens

    def _emit_chunk(
        self,
        paras,
        document_id,
        normalization_version,
        start_char,
        end_char,
        para_start,
        para_end,
        chunk_index,
    ) -> Chunk:

        text = "\n\n".join(p[0] for p in paras)

        chunk_id_tuple = generate_chunk_id(
            document_id=document_id,
            start_char=start_char,
            end_char=end_char,
            paragraph_start=para_start,
            paragraph_end=para_end,
            normalization_version=normalization_version,
            chunk_version=self.chunk_version,
        )

        # Extract just the hash ID (first element of tuple)
        chunk_id = (
            chunk_id_tuple[0] if isinstance(chunk_id_tuple, tuple) else chunk_id_tuple
        )

        return Chunk(
            chunk_id=chunk_id,
            document_id=document_id,
            text=text,
            start_char=start_char,
            end_char=end_char,
            paragraph_start=para_start,
            paragraph_end=para_end,
            chunk_index=chunk_index,
            chunk_version=self.chunk_version,
        )


def split_paragraphs(text: str) -> List[Tuple[str, int, int]]:
    paragraphs = []
    cursor = 0

    for match in re.finditer(r"(.*?)(\n\n+|$)", text, flags=re.S):
        para = match.group(1).strip()
        if not para:
            cursor = match.end()
            continue

        start = match.start(1)
        end = match.end(1)
        paragraphs.append((para, start, end))
        cursor = match.end()

    return paragraphs


def generate_chunk_id(
    document_id: str,
    start_char: int,
    end_char: int,
    paragraph_start: int,
    paragraph_end: int,
    normalization_version: str,
    chunk_version: str,
    debug=True,
) -> Tuple[str, str]:
    canonical = (
        f"doc:{document_id}"
        f"|norm:{normalization_version}"
        f"|chunk:{chunk_version}"
        f"|char:{start_char}-{end_char}"
        f"|para:{paragraph_start}-{paragraph_end}"
    )
    hash_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return (hash_id, canonical) if debug else hash_id


def estimate_tokens(text: str) -> int:
    # Rough but stable: ~0.75 tokens per word
    return int(len(text.split()) * TOKENS_PER_WORD)
