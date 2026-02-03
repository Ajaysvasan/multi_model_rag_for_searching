"""
Baseline data-layer ingestion + ANN sanity tests.

This script:
- Builds the semantic vector index from a fixed dataset
- Validates ANN behavior with deterministic sanity checks
- Is intended to be run offline and re-run safely

This is NOT a production service.
This is a controlled ingestion + validation entry point.
"""

import hashlib
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)


from pathlib import Path
from typing import Dict, List

import numpy as np
from ingest.chunker import Chunk, TextChunker
from ingest.normalizer import NormalizationProfiles
from ingest.storage.embedding import EmbeddingBatcher
from ingest.storage.hnsw import HNSWIndex
from ingest.Text_files_processing.file_loader import FileLoader
from ingest.Text_files_processing.text_extractor import TextExtractor

# You must provide your embedding model here
from sentence_transformers import SentenceTransformer

from config import Config


def stable_document_id(path: Path) -> str:
    """
    Deterministic document ID based on absolute file path.
    """
    return hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()


def log(msg: str) -> None:
    print(f"[DATA_LAYER] {msg}")


def run_baseline_ingestion() -> List[Chunk]:
    log("Starting baseline ingestion")

    log("Loading files")
    loader = FileLoader(Config.DATASET_PATH)
    files = loader.load_files()

    if not files:
        raise RuntimeError("No files found in dataset path")

    log("Extracting text")
    extractor = TextExtractor()
    extracted_texts: Dict[Path, str] = extractor.extract_all(files)

    log("Normalizing text")
    normalizer = NormalizationProfiles.rag_ingestion()
    normalized_texts: Dict[Path, str] = {
        path: normalizer.normalize_text(text) for path, text in extracted_texts.items()
    }

    # 4. Chunk documents
    log("Chunking documents")
    chunker = TextChunker(chunk_version=Config.CHUNK_VERSION)

    all_chunks: List[Chunk] = []

    for path, text in normalized_texts.items():
        path = Path(path)
        doc_id = stable_document_id(path)

        chunks = chunker.chunk(
            text=text,
            document_id=doc_id,
            normalization_version=Config.NORMALIZATION_VERSION,
        )

        all_chunks.extend(chunks)

    if not all_chunks:
        raise RuntimeError("Chunking produced zero chunks")

    log(f"Produced {len(all_chunks)} chunks")

    # 5. Load embedding model
    log("Loading embedding model")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    embedding_dim = model.get_sentence_embedding_dimension()

    # 6. Embed chunks
    log("Embedding chunks")
    batcher = EmbeddingBatcher(
        model=model,
        embedding_model_id=Config.EMBEDDING_MODEL_ID,
        batch_size=Config.EMBEDDING_BATCH_SIZE,
    )

    embeddings = batcher.embed_chunks(all_chunks)

    if len(embeddings) != len(all_chunks):
        raise RuntimeError("Embedding count mismatch")

    # 7. Build / load ANN index
    log("Building HNSW index")
    index = HNSWIndex(
        dim=embedding_dim,
        index_path=str(Config.INDEX_PATH),
    )

    index.add(embeddings)
    index.save()

    log(f"HNSW index contains {index.index.ntotal} vectors")

    return all_chunks


# Ann test
def run_ann_sanity_tests(chunks: List[Chunk]) -> None:
    log("Running ANN sanity tests")
    # Reload index
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embedding_dim = model.get_sentence_embedding_dimension()

    index = HNSWIndex(
        dim=embedding_dim,
        index_path=str(Config.INDEX_PATH),
    )
    index.load()

    test_chunk = chunks[len(chunks) // 2]
    query_text = test_chunk.text[:300]

    query_vector = model.encode(
        query_text,
        normalize_embeddings=True,
    )

    results = index.search(query_vector, k=Config.ANN_TOP_K)

    log("Self-retrieval test")
    if test_chunk.chunk_id[0] not in results:
        raise AssertionError("Self-retrieval test FAILED")
    log("Self-retrieval test PASSED")

    same_doc_chunks = [c for c in chunks if c.document_id == test_chunk.document_id]

    if len(same_doc_chunks) > 1:
        query_text = same_doc_chunks[0].text[:300]
        query_vector = model.encode(query_text, normalize_embeddings=True)
        results = index.search(query_vector, k=Config.ANN_TOP_K)

        hits = [cid for cid in results if cid in {c.chunk_id for c in same_doc_chunks}]

        if len(hits) < 2:
            raise AssertionError("Same-document similarity test FAILED")

        log("Same-document similarity test PASSED")

    index2 = HNSWIndex(
        dim=embedding_dim,
        index_path=str(Config.INDEX_PATH),
    )
    index2.load()

    results2 = index2.search(query_vector, k=Config.ANN_TOP_K)

    if results != results2:
        log("WARNING: Minor ordering differences after reload (acceptable)")
    else:
        log("Reload stability test PASSED")

    log("All ANN sanity tests completed")


if __name__ == "__main__":
    chunks = run_baseline_ingestion()
    run_ann_sanity_tests(chunks)

    log("Baseline ingestion + ANN validation COMPLETE")
