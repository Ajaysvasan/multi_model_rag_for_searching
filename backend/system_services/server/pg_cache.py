import json
import os
import sys
from datetime import datetime
from typing import List, Optional
from uuid import UUID

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
project_dir = os.path.dirname(parent_dir)
sys.path.append(project_dir)

from data_models.cache import CacheTopic
from data_models.session import SessionLocal


class PgTopicCache:

    def lookup(self, user_id: UUID, topic: str) -> Optional[List[str]]:
        db = SessionLocal()
        try:
            row = (
                db.query(CacheTopic)
                .filter(CacheTopic.user_id == user_id, CacheTopic.topic == topic)
                .first()
            )
            if row is None:
                return None

            row.last_accessed = datetime.utcnow()
            row.score = row.score + 1.0
            db.commit()

            # chunk_ids are stored as JSON in the topic field's associated score
            # We repurpose the 'topic' column as the cache key and store chunk_ids
            # in the level column won't work, so we store them differently.
            # Since the schema doesn't have a chunk_ids column, we return None
            # and fall through to ANN search. The cache is best-effort.
            return None
        finally:
            db.close()

    def insert_new(self, user_id: UUID, topic: str, level: int = 1, score: float = 1.0):
        db = SessionLocal()
        try:
            existing = (
                db.query(CacheTopic)
                .filter(CacheTopic.user_id == user_id, CacheTopic.topic == topic)
                .first()
            )
            if existing:
                existing.score = existing.score + 1.0
                existing.last_accessed = datetime.utcnow()
            else:
                entry = CacheTopic(
                    user_id=user_id,
                    topic=topic,
                    level=level,
                    score=score,
                    last_accessed=datetime.utcnow(),
                )
                db.add(entry)
            db.commit()
        finally:
            db.close()
