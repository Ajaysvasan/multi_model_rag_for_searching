from db.base import Base
from sqlalchemy import Column, DateTime, Float, ForeignKey, SmallInteger, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func


class CacheTopic(Base):
    __tablename__ = "cache_topics"
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    topic = Column(Text, primary_key=True)
    level = Column(SmallInteger, nullable=False)
    score = Column(Float, nullable=False)
    last_accessed = Column(DateTime, nullable=False, server_default=func.now())
