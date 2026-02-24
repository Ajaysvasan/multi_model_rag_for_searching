from uuid import UUID


class _UserConvMemoryAdapter:
    """Adapts PgConversationMemory to the ConversationMemory interface."""

    def __init__(self, pg_mem, user_id: UUID):
        self._pg = pg_mem
        self._uid = user_id

    def add_turn(self, session_id, role, content):
        self._pg.add_turn(self._uid, session_id, role, content)

    def get_context(self, session_id, max_turns=None):
        return self._pg.get_context(self._uid, session_id, max_turns)

    def get_recent_queries(self, session_id, max_queries=3):
        return self._pg.get_recent_queries(self._uid, session_id, max_queries)

    def close(self):
        pass
