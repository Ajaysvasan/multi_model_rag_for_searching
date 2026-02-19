import uuid

from db.base import Base
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func


class Document(Base):
    __tablename__ = "documents"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(Text, nullable=False)
    original_path = Column(Text)
    modality = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(Text, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    start_char = Column(Integer, nullable=False)
    end_char = Column(Integer, nullable=False)
    text = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class Embedding(Base):
    __tablename__ = "embeddings"
    chunk_id = Column(Text, ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    faiss_id = Column(BigInteger, nullable=False)
