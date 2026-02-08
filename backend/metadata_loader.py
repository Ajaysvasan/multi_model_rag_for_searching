import json
from typing import Dict

from data_layer.chunkstore.Chunkstore import ChunkMetadataStore


def load_metadata_store(metadata_path: str) -> ChunkMetadataStore:
    store = ChunkMetadataStore()

    with open(metadata_path, "r", encoding="utf-8") as f:
        data: Dict[str, Dict] = json.load(f)

    for chunk_id, meta in data.items():
        store.add(chunk_id, meta)

    return store
