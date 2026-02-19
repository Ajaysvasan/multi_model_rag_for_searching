import os
import sys
from typing import Dict, List, Optional
from uuid import UUID

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
project_dir = os.path.dirname(parent_dir)
sys.path.append(project_dir)

from sqlalchemy import func

from data_models.history import HistorySession, HistoryTurn
from data_models.session import SessionLocal


class PgConversationMemory:
    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns

    def _get_or_create_session(self, db, user_id: UUID, session_id: str) -> UUID:
        session_uuid = None
        try:
            session_uuid = UUID(session_id)
        except (ValueError, AttributeError):
            pass

        if session_uuid:
            existing = (
                db.query(HistorySession)
                .filter(HistorySession.id == session_uuid, HistorySession.user_id == user_id)
                .first()
            )
            if existing:
                return existing.id

        new_session = HistorySession(user_id=user_id)
        db.add(new_session)
        db.flush()
        return new_session.id

    def add_turn(self, user_id: UUID, session_id: str, role: str, content: str):
        db = SessionLocal()
        try:
            db_session_id = self._get_or_create_session(db, user_id, session_id)

            max_idx = (
                db.query(func.max(HistoryTurn.turn_index))
                .filter(HistoryTurn.session_id == db_session_id, HistoryTurn.user_id == user_id)
                .scalar()
            )
            next_idx = (max_idx or 0) + 1

            turn = HistoryTurn(
                session_id=db_session_id,
                user_id=user_id,
                turn_index=next_idx,
                query_text=f"{role}: {content}",
            )
            db.add(turn)
            db.commit()

            self._trim(db, user_id, db_session_id)
        finally:
            db.close()

    def get_context(self, user_id: UUID, session_id: str, max_turns: Optional[int] = None) -> List[Dict]:
        limit = max_turns or self.max_turns
        db = SessionLocal()
        try:
            session_uuid = None
            try:
                session_uuid = UUID(session_id)
            except (ValueError, AttributeError):
                return []

            rows = (
                db.query(HistoryTurn)
                .filter(HistoryTurn.session_id == session_uuid, HistoryTurn.user_id == user_id)
                .order_by(HistoryTurn.turn_index.desc())
                .limit(limit)
                .all()
            )

            result = []
            for row in reversed(rows):
                text = row.query_text
                if text.startswith("user: "):
                    result.append({"role": "user", "content": text[6:]})
                elif text.startswith("assistant: "):
                    result.append({"role": "assistant", "content": text[11:]})
                else:
                    result.append({"role": "user", "content": text})
            return result
        finally:
            db.close()

    def get_recent_queries(self, user_id: UUID, session_id: str, max_queries: int = 3) -> List[str]:
        db = SessionLocal()
        try:
            session_uuid = None
            try:
                session_uuid = UUID(session_id)
            except (ValueError, AttributeError):
                return []

            rows = (
                db.query(HistoryTurn)
                .filter(
                    HistoryTurn.session_id == session_uuid,
                    HistoryTurn.user_id == user_id,
                    HistoryTurn.query_text.like("user: %"),
                )
                .order_by(HistoryTurn.turn_index.desc())
                .limit(max_queries)
                .all()
            )

            return [row.query_text[6:] for row in reversed(rows)]
        finally:
            db.close()

    def _trim(self, db, user_id: UUID, session_id: UUID):
        count = (
            db.query(func.count(HistoryTurn.id))
            .filter(HistoryTurn.session_id == session_id, HistoryTurn.user_id == user_id)
            .scalar()
        )

        if count > self.max_turns * 2:
            excess = count - self.max_turns
            old_ids = (
                db.query(HistoryTurn.id)
                .filter(HistoryTurn.session_id == session_id, HistoryTurn.user_id == user_id)
                .order_by(HistoryTurn.turn_index.asc())
                .limit(excess)
                .all()
            )
            ids_to_delete = [r[0] for r in old_ids]
            if ids_to_delete:
                db.query(HistoryTurn).filter(HistoryTurn.id.in_(ids_to_delete)).delete(synchronize_session=False)
                db.commit()
