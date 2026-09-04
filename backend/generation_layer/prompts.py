"""Prompt text and context assembly.

The generation system prompt lives here as a single constant. It used to be
duplicated verbatim in LlamaGenerator and MmapGenerator as twelve numbered
rules, several of which restated each other (2/11, 3/12, 4/10, and 6-9 were
four ways of saying "do not invent things"). That cost ~250 tokens of prefill
on every single query for no behavioural gain. The version below preserves
every behaviour the code actually depends on -- inline [n] citations for
_extract_cited_indices, the "could not find" wording for _is_refusal, and the
no-References instruction for _clean_response -- in roughly a third the tokens.
"""

import logging

logger = logging.getLogger("generation")

# ~95 tokens, down from ~250. Keep the refusal sentence byte-identical to the
# phrases in LlamaGenerator._REFUSAL_PHRASES or refusal detection breaks.
SYSTEM_PROMPT = """You are a factual Q&A assistant. Answer ONLY from the CONTEXT passages below.

1. Use only facts stated in the context. Never invent URLs, links, dates, statistics, or references.
2. Cite inline as [1], [2] after every factual claim, and cite every passage you used.
3. If the context does not answer the question, reply with exactly: "I could not find relevant information in the available sources." and cite nothing.
4. Be concise. Do not add References, Sources, or Bibliography sections, and never mention file formats, PDF metadata, or how the documents were made."""


def wrap_prompt(system_message: str, user_message: str, template: str = None) -> str:
    """Apply a model's chat template.

    Only needed by the C++ backend, which has no template of its own.
    llama-cpp-python reads the template out of the GGUF and does this itself.

    Getting this wrong is quiet rather than loud -- the model still produces
    fluent text, it just stops following the instructions -- so the template
    tracks Config.PROMPT_TEMPLATE alongside the model choice.
    """
    from config import Config

    template = (template or getattr(Config, "PROMPT_TEMPLATE", "plain")).lower()

    if template == "mistral":
        return f"[INST] <<SYS>>\n{system_message}\n<</SYS>>\n\n{user_message} [/INST]"
    if template == "zephyr":
        # StableLM-Zephyr / Zephyr / TinyLlama-chat family
        return (
            f"<|system|>\n{system_message}<|endoftext|>\n"
            f"<|user|>\n{user_message}<|endoftext|>\n"
            f"<|assistant|>\n"
        )
    return f"{system_message}\n\n{user_message}\n\nAnswer:"


def estimate_tokens(text: str) -> int:
    """Cheap upper-ish bound on token count.

    Deliberately not a real tokenizer: this runs before the model is loaded and
    is only used to decide how many passages fit. ~3.6 chars/token is
    conservative for English, which is what we want when the cost of guessing
    low is a prompt that overruns n_ctx.
    """
    return int(len(text) / 3.6) + 1


SYSTEM_PROMPTS = {
    "answer_with_citations": """You are a helpful assistant that answers questions based on provided context.

RULES:
1. ONLY use information from the provided context chunks to answer the question.
2. Include inline citations using [1], [2], etc. referencing the source chunks.
3. If the context doesn't contain enough information, say "Based on the available information, I cannot fully answer this question."
4. Be concise but comprehensive.
5. NEVER invent URLs, web links, references, or facts not present in the context.
6. NEVER generate fake citations or references to external websites.
7. Do NOT add a "References" or "Sources" section - citations are handled separately.

CONTEXT CHUNKS:
{context}

USER QUESTION: {query}

Provide your answer with inline citations:""",
    "query_reformulation": """Given the following query that didn't retrieve relevant results, 
generate a reformulated query that might work better.

Original query: {query}

Provide only the reformulated query, nothing else:""",
    "relevance_check": """Determine if the following text chunk is relevant to the user's query.

Query: {query}

Chunk:
{chunk_text}

Respond with only:
RELEVANT: <confidence 0-100>
or
NOT_RELEVANT: <confidence 0-100>""",
}


def format_context_for_generation(
    chunks: list,
    include_source: bool = True,
    max_chunks: int = 5,
    token_budget: int = None,
    char_limit: int = 1000,
) -> str:
    """
    Format chunks into a context string for LLM generation.

    Args:
        chunks: List of chunk dictionaries
        include_source: Whether to include source file paths
        max_chunks: Maximum number of chunks to include
        token_budget: Stop adding passages once this many estimated tokens are
            used. None keeps the old unbounded behaviour.
        char_limit: Per-passage truncation length

    Returns:
        Formatted context string with citation markers
    """
    formatted_parts = []
    used_tokens = 0
    dropped = 0

    for i, chunk in enumerate(chunks[:max_chunks], 1):
        text = chunk.get("chunk_text", chunk.get("text", "")).strip()

        # Skip empty chunks or error markers
        if not text or (text.startswith("[") and text.endswith("]")):
            continue

        # Truncate very long chunks to keep context manageable
        if len(text) > char_limit:
            text = text[:char_limit] + "..."

        source = chunk.get("source_path", "unknown")
        modality = chunk.get("modality", "unknown").upper()

        if include_source:
            source_name = source.split("/")[-1] if "/" in source else source
            part = (
                f"=== PASSAGE [{i}] ==="
                f"\nSource: {source_name} | Type: {modality}"
                f"\n{text}"
            )
        else:
            part = f"=== PASSAGE [{i}] ===" f"\nType: {modality}" f"\n{text}"

        # Stop before the prompt can overrun n_ctx. Previously five chunks were
        # concatenated unconditionally, so a run of large chunks could build a
        # prompt longer than the context window -- llama.cpp then raises and the
        # query fails with "Error: ..." instead of answering.
        if token_budget is not None:
            cost = estimate_tokens(part) + 2  # +2 for the blank-line separator
            if used_tokens + cost > token_budget:
                dropped = len(chunks[:max_chunks]) - len(formatted_parts)
                break
            used_tokens += cost

        formatted_parts.append(part)

    if dropped > 0:
        logger.info(
            f"Context budget {token_budget} tok: kept {len(formatted_parts)} "
            f"passage(s), dropped {dropped} that would not fit"
        )

    return "\n\n".join(formatted_parts)
