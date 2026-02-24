from uuid import UUID


class _UserCacheAdapter:
    """Adapts PgTopicCache to the TopicCacheManager interface RetrievalEngine expects."""

    def __init__(self, pg_cache, user_id: UUID):
        self._pg = pg_cache
        self._uid = user_id

    def lookup(self, key):
        self._pg.lookup(self._uid, key.topic_label)
        return None

    def insert_new(self, key, cached_chunk_ids=None):
        self._pg.insert_new(self._uid, key.topic_label)
