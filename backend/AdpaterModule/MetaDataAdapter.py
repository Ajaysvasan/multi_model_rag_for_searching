from uuid import UUID


class _UserMetadataAdapter:
    """Adapts PgChunkStore to the ChunkMetadataStore interface."""

    def __init__(self, pg_store, user_id: UUID):
        self._pg = pg_store
        self._uid = user_id

    def get_by_ids(self, chunk_ids):
        return self._pg.get_by_ids(chunk_ids, self._uid)

    def count_chunks(self):
        return 0

    def has_chunk(self, chunk_id):
        result = self._pg.get_by_ids([chunk_id], self._uid)
        return len(result) > 0
