import uuid

from db.base import Base
from sqlalchemy import VARCHAR, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func


class User(Base):
    __tablename__ = "users"
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        index=True,
        server_default=func.uuid_generate_v4(),
    )
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    username = Column(VARCHAR(255), unique=True, index=True)
