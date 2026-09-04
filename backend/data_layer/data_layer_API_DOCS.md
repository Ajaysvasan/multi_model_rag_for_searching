# data_layer — API reference

[← Back to BACKEND.md](../BACKEND.md) · [Design notes](data_layer.md)

## End-to-end ingestion

```python
from pathlib import Path
from sentence_transformers import SentenceTransformer

from config import Config
from data_layer.ingest.Text_files_processing.file_loader import FileLoader
from data_layer.ingest.Text_files_processing.text_extractor import TextExtractor
from data_layer.ingest.normalizer import NormalizationProfiles
from data_layer.ingest.chunker import TextChunker
from data_layer.ingest.storage.embedding import EmbeddingRecord
from data_layer.ingest.storage.hnsw import HNSWIndex
from data_layer.chunkstore.Chunkstore import ChunkMetadataStore

model = SentenceTransformer(Config.EMBED_MODEL_NAME)
dim = model.get_sentence_embedding_dimension()

files = FileLoader(Path("data/datasets")).load_files()
texts = TextExtractor().extract_all(
    {k: v for k, v in files.items() if k in ("docs", "txt", "pdf")}
)
normalized = NormalizationProfiles.rag_ingestion().normalize_all(texts)

chunker = TextChunker(
    target_tokens=Config.CHUNK_SIZE,
    max_tokens=int(Config.CHUNK_SIZE * 1.25),
    overlap_tokens=Config.CHUNK_OVERLAP,
)

index = HNSWIndex(dim=dim, index_path=Config.INDEX_PATH)
store = ChunkMetadataStore(db_path=Config.METADATA_DB_PATH)

records, rows = [], []
for path, text in normalized.items():
    for ch in chunker.chunk(text, document_id=str(path),
                            normalization_version=Config.NORMALIZATION_VERSION):
        if ch.chunk_id in index:          # idempotent: skip what we already have
            continue
        vec = model.encode(ch.text, normalize_embeddings=True)
        records.append(EmbeddingRecord(
            embedding_id=ch.chunk_id, chunk_id=ch.chunk_id,
            document_id=ch.document_id, vector=vec.tolist(),
            embedding_model_id=Config.EMBEDDING_MODEL_ID, embedding_dim=dim,
        ))
        rows.append({
            "chunk_id": ch.chunk_id, "document_id": ch.document_id,
            "source_path": str(Path(path).resolve()), "modality": "text",
            "chunk_index": ch.chunk_index,
            "start_offset": ch.start_char, "end_offset": ch.end_char,
            "chunk_version": ch.chunk_version,
            "normalization_version": Config.NORMALIZATION_VERSION,
            "chunk_text": ch.text,
        })

index.add(records)
index.save()
store.insert_many(rows)
store.close()
```

## `TextChunker`

```python
chunker = TextChunker(target_tokens=256, max_tokens=320, overlap_tokens=50)
chunks = chunker.chunk(text, document_id="doc-1", normalization_version="rag_v1")
```

`Chunk`: `chunk_id`, `document_id`, `text`, `start_char`, `end_char`,
`paragraph_start`, `paragraph_end`, `chunk_index`, `chunk_version`.

```python
from data_layer.ingest.chunker import estimate_tokens, generate_chunk_id, split_paragraphs

estimate_tokens("four words go here")          # 3  (0.75 tokens/word)
split_paragraphs(text)                          # [(text, start, end), ...]
generate_chunk_id(document_id="d", start_char=0, end_char=100,
                  paragraph_start=0, paragraph_end=1,
                  normalization_version="rag_v1", chunk_version="chunk_v1")
# -> (sha256_hex, canonical_string)
```

## `HNSWIndex`

```python
index = HNSWIndex(dim=384, index_path=Path("data/index/faiss_hnsw.index"),
                  M=32, ef_construction=200, ef_search=64)

index.add(records)         # skips IDs already present
index.save()               # writes .index and .index.ids together
index.load()               # asserts the two agree in length

"chunk-id" in index        # membership test
ids = index.search(query_vector, k=10)   # -> list[str]
```

| Method | Notes |
|---|---|
| `add(list[EmbeddingRecord])` | Deduplicates by `embedding_id`; raises on a dimension mismatch |
| `search(vector, k)` | Normalises the query; raises on a dimension mismatch |
| `save()` / `load()` | The `.ids` sidecar is mandatory; `load` raises without it |

## `ChunkMetadataStore`

```python
store = ChunkMetadataStore(db_path=Path("data/index/chunks.db"))
store.insert_many(rows)                  # INSERT OR IGNORE -- idempotent
rows = store.get_by_ids(["c1", "c2"])    # preserves the input order
store.count_chunks()
store.has_chunk("c1")
store.close()
```

Input order is preserved on `get_by_ids` because downstream reranking depends on
it. Missing IDs are skipped silently.

## Images and audio

```python
from data_layer.ingest.ImageProcessing.image_ingestion import ingest_images
from data_layer.ingest.audio_processing.audio_ingestion import ingest_audio

records = ingest_images(["/photos/a.png"])
# [{chunk_id, document_id, source_path, modality: "image", chunk_text: "[Image: ...]\n<ocr>", ...}]

transcripts = ingest_audio(["/audio/a.mp3"], model_name="small", model_dir="./models/whisper")
# {"/abs/path/a.mp3": "transcribed text"}
```

Both swallow per-file errors and skip the file rather than aborting the batch.
Audio transcripts join the text pipeline and are chunked normally.

## Configuration

| `Config` key | Default | Meaning |
|---|---|---|
| `CHUNK_SIZE` | 256 | Target tokens per chunk |
| `CHUNK_OVERLAP` | 50 | Overlap tokens carried forward |
| `EMBED_MODEL_NAME` | `all-MiniLM-L6-v2` | Embedding model (dim 384) |
| `EMBEDDING_BATCH_SIZE` | 64 | Batch size for `EmbeddingBatcher` |
| `INDEX_PATH` | `data/index/faiss_hnsw.index` | Index file |
| `METADATA_DB_PATH` | `data/index/chunks.db` | SQLite metadata |
| `NORMALIZATION_VERSION` / `CHUNK_VERSION` | `rag_v1` / `chunk_v1` | Change to force a re-index |

## Repairing missing chunk text

Older rows may lack `chunk_text`. Retrieval drops such chunks rather than
guessing at source bytes:

```bash
python backfill_chunks.py
```
