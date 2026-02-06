from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class EmbeddingRecord:
    embedding_id: str  # usually == chunk_id
    chunk_id: str
    document_id: str
    vector: List[float]
    embedding_model_id: str
    embedding_dim: int


class EmbeddingBatcher:
    def __init__(
        self,
        model,
        embedding_model_id: str,
        batch_size: int = 64,
    ):
        self.model = model
        self.embedding_model_id = embedding_model_id
        self.batch_size = batch_size

    def embed_chunks(self, chunks: list) -> list[EmbeddingRecord]:
        records: list[EmbeddingRecord] = []

        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i : i + self.batch_size]
            texts = [c.text for c in batch]

            vectors = self.model.encode(
                texts,
                show_progress_bar=False,
                normalize_embeddings=True,
            )

            for chunk, vector in zip(batch, vectors):
                records.append(
                    EmbeddingRecord(
                        embedding_id=chunk.chunk_id,
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        vector=vector.tolist(),
                        embedding_model_id=self.embedding_model_id,
                        embedding_dim=len(vector),
                    )
                )

        return records
