import os

import faiss
import numpy as np

try:
    from storage.embedding import EmbeddingRecord
except Exception as e:
    raise ImportError(f"The following exception occured: \n{e}")


class HNSWIndex:
    def __init__(
        self,
        dim: int,
        index_path: str,
        M: int = 32,
        ef_construction: int = 200,
        ef_search: int = 64,
    ):
        self.dim = dim
        self.index_path = index_path
        self.M = M
        self.ef_construction = ef_construction
        self.ef_search = ef_search

        self.index = faiss.IndexHNSWFlat(dim, M)
        self.index.hnsw.efConstruction = ef_construction
        self.index.hnsw.efSearch = ef_search

        # Map faiss IDs → embedding_ids
        self.id_map: list[str] = []

        # Track known IDs for idempotent ingestion
        self._known_ids: set[str] = set()

    def add(self, embeddings: list[EmbeddingRecord]) -> None:
        if not embeddings:
            return

        # Filter out duplicates and validate dimensions
        valid_embeddings = []
        for e in embeddings:
            # Skip duplicates for idempotent ingestion
            if e.embedding_id in self._known_ids:
                continue

            # Validate dimension
            if len(e.vector) != self.dim:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {self.dim}, "
                    f"got {len(e.vector)} for ID {e.embedding_id}"
                )

            valid_embeddings.append(e)
            self._known_ids.add(e.embedding_id)
            self.id_map.append(e.embedding_id)

        if not valid_embeddings:
            return

        vectors = np.array([e.vector for e in valid_embeddings], dtype="float32")
        self.index.add(vectors)

    def search(self, query_vector, k: int = 5) -> list[str]:
        # Validate query dimension
        if len(query_vector) != self.dim:
            raise ValueError(
                f"Query dimension mismatch: expected {self.dim}, got {len(query_vector)}"
            )

        # Set efSearch dynamically based on k (industry standard)
        self.index.hnsw.efSearch = max(self.ef_search, k * 4)

        vector = np.array([query_vector], dtype="float32")

        # Normalize query vector for consistent cosine similarity
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        distances, indices = self.index.search(vector, k)

        results = []
        for idx in indices[0]:
            if idx < 0:
                continue
            results.append(self.id_map[idx])

        return results

    def save(self) -> None:
        faiss.write_index(self.index, self.index_path)

        # Save ID mapping
        with open(self.index_path + ".ids", "w") as f:
            for eid in self.id_map:
                f.write(eid + "\n")

    def load(self) -> None:
        if not os.path.exists(self.index_path):
            return

        self.index = faiss.read_index(self.index_path)

        # Load ID mapping
        ids_path = self.index_path + ".ids"
        if not os.path.exists(ids_path):
            raise FileNotFoundError(
                f"ID mapping file not found: {ids_path}. "
                f"Index cannot be used without ID mapping."
            )

        with open(ids_path) as f:
            self.id_map = [line.strip() for line in f]

        # Critical: Guard against index/id_map mismatch
        assert self.index.ntotal == len(self.id_map), (
            f"FAISS index and id_map size mismatch: "
            f"index has {self.index.ntotal} vectors, "
            f"but id_map has {len(self.id_map)} IDs. "
            f"This indicates corruption or incomplete save/load."
        )

        # Rebuild known_ids set for idempotent additions after load
        self._known_ids = set(self.id_map)
