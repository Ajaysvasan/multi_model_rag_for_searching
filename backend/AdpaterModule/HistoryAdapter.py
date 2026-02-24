from uuid import UUID


class _UserHistoryAdapter:
    """Adapts PgConversationHistory to the ConversationHistory interface."""

    def __init__(self, pg_history, user_id: UUID):
        self._pg = pg_history
        self._uid = user_id

    def find_similar(self, query_embedding):
        return self._pg.find_similar(self._uid, query_embedding)

    def add_or_update(self, topic_key, query_embedding, chunk_ids):
        self._pg.add_or_update(
            self._uid, topic_key.topic_label, query_embedding, chunk_ids
        )
