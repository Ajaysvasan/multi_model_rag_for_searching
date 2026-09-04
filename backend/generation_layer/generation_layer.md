# generation_layer — grounded answer synthesis

[← Back to BACKEND.md](../BACKEND.md) · [API reference](generation_layer_API_DOCS.md)

Turns retrieved passages into a prose answer whose every claim carries a
citation back to a specific chunk.

## The problem

A language model handed some passages and a question will produce fluent text
whether or not the passages contain the answer. Three failure modes matter:

1. **Fabricated sources.** Models append plausible-looking "References"
   sections, URLs, and `(Author, 2023)` citations that do not exist.
2. **Uncited claims.** An answer without inline markers cannot be traced, which
   defeats the point of retrieval.
3. **Answering anyway.** Asked something the corpus does not cover, a model
   would rather guess than refuse.

## Design

### Two interchangeable backends

| | `LlamaGenerator` | `MmapGenerator` |
|---|---|---|
| Inference | in-process `llama-cpp-python` | C++ worker over a pipe |
| Chat template | read from the GGUF | applied by hand via `Config.PROMPT_TEMPLATE` |
| Failure blast radius | takes the API process with it | worker only |
| Default | yes | opt-in |

Both expose the same `generate()` signature and return the same
`GenerationResult`, so the retrieval layer does not care which is in use.

### Context budgeting

The prompt is assembled against the real context window rather than assuming a
fixed number of passages fits:

```
budget = n_ctx − tokens(system + question + history) − max_new_tokens − safety_margin
```

Passages are added until the budget is exhausted; the rest are dropped with a
log line. Without this, raising `MAX_CONTEXT_CHUNKS` silently produces prompts
longer than `n_ctx` and llama.cpp raises instead of answering. At the default of
5 chunks the budget is a no-op safety net; it earns its place the moment the
knob is turned.

`estimate_tokens` deliberately over-estimates (~3.6 chars/token). It runs before
the model loads, so a real tokenizer is not available, and guessing high is the
safe direction.

### Prompt economy

The system prompt is one constant in `prompts.py`. It was previously twelve
numbered rules duplicated verbatim in both generator classes, where rules 2/11,
3/12, 4/10 and 6–9 restated each other — **322 tokens**, re-sent and re-prefilled
on every query. The current four-rule version measures **144 tokens**, saving
178 tokens of prefill per request while preserving every behaviour the code
depends on:

| Rule | Depended on by |
|---|---|
| Inline `[n]` citations | `_extract_cited_indices` |
| Exact refusal wording | `_is_refusal` |
| No References/Sources sections | `_clean_response` |

### Post-processing

Three passes run on every answer:

- **`_clean_response`** truncates at any "References:"/"Bibliography:" marker,
  strips URLs, `Retrieved from …` lines, and `(Author, 2023)` citations.
- **`_is_refusal`** decides whether the model declined. This gates citations: a
  refusal must carry none, or the UI shows sources for a non-answer. Detection
  matches both a phrase list and a shape-matching regex, and — critically —
  **only against the first sentence**. A real answer may legitimately say "the
  passages do not mention ultrasound, but describe MRI [2]" in its second
  sentence; refusals lead with the refusal.
- **`_extract_cited_indices`** parses the `[n]` markers the model actually
  emitted, and citations are filtered to those. A model given five passages that
  uses two returns two citations, not five.

## Trade-offs

- **Over-citation is tolerated.** A model that cites `[1][2][3]` where `[1]`
  would do costs precision but shows real passages. For a source-backed search
  tool, an extra source is far less harmful than a missing one.
- **Refusal detection is heuristic.** A false positive strips citations from a
  valid answer (the text survives); a false negative shows fabricated sources.
  The first-sentence rule was chosen to bias toward the recoverable error.
