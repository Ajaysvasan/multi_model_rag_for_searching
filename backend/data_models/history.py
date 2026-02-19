from db.base import Base
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func


class HistorySession(Base):
    __tablename__ = "history_sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class HistoryTurn(Base):
    __tablename__ = "history_turns"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    session_id = Column(UUID(as_uuid=True), ForeignKey("history_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    turn_index = Column(Integer, nullable=False)
    query_text = Column(Text, nullable=False)
    query_embedding_ref = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
