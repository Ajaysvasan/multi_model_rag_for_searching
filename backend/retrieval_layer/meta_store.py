from typing import Any, Dict, List


class ChunkMetadataStore:
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def add(self, chunk_id: str, meta: Dict[str, Any]) -> None:
        self._store[chunk_id] = meta

    def get_many(self, chunk_ids: List[str]) -> List[Dict[str, Any]]:
        results = []
        for cid in chunk_ids:
            if cid in self._store:
                results.append(self._store[cid])
        return results
