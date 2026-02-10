"""
Prompt templates for answer generation.
"""

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

def format_context_for_generation(chunks: list, include_source: bool = True, max_chunks: int = 5) -> str:
    """
    Format chunks into a context string for LLM generation.
    
    Args:
        chunks: List of chunk dictionaries
        include_source: Whether to include source file paths
        max_chunks: Maximum number of chunks to include
        
    Returns:
        Formatted context string with citation markers
    """
    formatted_parts = []
    
    for i, chunk in enumerate(chunks[:max_chunks], 1):
        text = chunk.get("chunk_text", chunk.get("text", "")).strip()
        
        # Skip empty chunks or error markers
        if not text or (text.startswith("[") and text.endswith("]")):
            continue
        
        # Truncate very long chunks to keep context manageable
        if len(text) > 1000:
            text = text[:1000] + "..."
        
        source = chunk.get("source_path", "unknown")
        if include_source:
            source_name = source.split("/")[-1] if "/" in source else source
            formatted_parts.append(f"[{i}] (Source: {source_name})\n{text}")
        else:
            formatted_parts.append(f"[{i}]\n{text}")
    
    return "\n\n---\n\n".join(formatted_parts)
