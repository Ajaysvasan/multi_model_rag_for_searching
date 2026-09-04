# data_layer — ingestion, chunking, indexing

[← Back to BACKEND.md](../BACKEND.md) · [API reference](data_layer_API_DOCS.md)

Everything between "a file on disk" and "a searchable vector".

## The problem

Source material arrives as PDFs, Word documents, plain text, photographs,
screenshots, and audio recordings. All of it has to become text, be cut into
retrievable pieces, and be embedded — without losing the thread back to the
original file, because every answer must cite a real location.

Three sub-problems:

1. **Extraction differs per format.** A PDF needs a text layer, a screenshot
   needs OCR, a recording needs transcription.
2. **Documents are too long to embed whole.** A 40-page report is one vector's
   worth of nothing. Cutting it up destroys context if done naively.
3. **Re-ingestion must be idempotent.** Users re-add folders. Doing so must not
   duplicate every chunk.

## Design

```
  files ─▶ FileLoader ─▶ TextExtractor ─▶ Normalizer ─▶ TextChunker ─▶ Embedder ─▶ HNSWIndex
                             │                                             │
                        OCR / Whisper                              ChunkMetadataStore
```

### Extraction

`FileLoader` walks a path and buckets files by extension into `docs`, `txt`,
`pdf`, `image`, `audio`. `TextExtractor` handles the text formats;
`ImageProcessing/` runs preprocessing, captioning and OCR;
`audio_processing/` runs Whisper transcription. Image and audio content becomes
ordinary text downstream, so one retrieval path serves every modality.

### Normalisation

`NormalizationProfiles.rag_ingestion()` collapses whitespace, fixes encodings,
and strips artefacts, stamped with `Config.NORMALIZATION_VERSION`. The version
matters: **chunk offsets refer to normalised text, not the raw file.** Anything
that later wants the source bytes must normalise the same way, which is why the
retrieval layer refuses to re-read source files for missing chunk text.

### Chunking

Paragraph-aware rather than fixed-window. Paragraphs accumulate until
`target_tokens` (256) would be exceeded, then a chunk is emitted with an overlap
tail carried into the next one, so a sentence spanning a boundary still appears
whole somewhere. A paragraph larger than `max_tokens` is split on sentence
boundaries with offsets tracked through the split.

Token counts are estimated at 0.75 tokens/word — stable and cheap, and no real
tokenizer is loaded during ingestion.

**Chunk IDs are content-addressed.** The ID is a SHA-256 of

```
doc:<document_id>|norm:<version>|chunk:<version>|char:<start>-<end>|para:<start>-<end>
```

so the same bytes chunked the same way always produce the same ID. That is what
makes re-ingestion idempotent: `HNSWIndex` skips IDs it already holds and the
metadata store uses `INSERT OR IGNORE`.

Changing `NORMALIZATION_VERSION` or `CHUNK_VERSION` deliberately changes every
ID, forcing a clean re-index.

> **Fixed defect.** The accumulation loop could spin forever: on emitting a
> chunk it did not advance the paragraph cursor, and if the overlap tail was the
> whole buffer, state was unchanged and the same chunk was emitted endlessly.
> The tail is now dropped when it leaves no room for the pending paragraph.

### Vector index

`HNSWIndex` wraps `faiss.IndexHNSWFlat` (M=32, efConstruction=200) and keeps a
parallel `id_map` from FAISS's integer positions back to chunk IDs. The index
and the `.ids` sidecar are saved together, and `load()` asserts they are the
same length — a torn save is loud rather than silently misattributing every
citation.

`efSearch` is raised to `max(ef_search, k*4)` at query time, trading a little
latency for recall.

## Trade-offs

- **Estimated tokens.** Cheap and consistent, but 0.75 tokens/word is wrong for
  code and non-English text, so real chunk sizes drift from the target.
- **`id_map` is a flat list.** Deletion would require rebuilding the index;
  there is no delete path today.
- **OCR and transcription quality bound everything.** A bad transcript produces
  a confidently retrievable wrong passage.
- **`data_layer_pipeline.py` is dead.** It references `Config.DATASET_PATH`
  (absent) and its collection loop appends each document's chunks once per
  chunk, producing n² duplicates. The live paths are
  `system_services/tui/ingestion_pipeline.py` and
  `system_services/server/ingestion_orchestrator.py`.
