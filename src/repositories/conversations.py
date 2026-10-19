import json
import uuid
from datetime import datetime, timezone

from src.db.database import Database


class ConversationRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def ensure(self, conversation_id: str | None, client_id: str) -> str:
        with self.db.connect() as conn:
            if conversation_id:
                row = conn.execute("SELECT client_id FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
                if row and row["client_id"] == client_id:
                    return conversation_id
            new_id = uuid.uuid4().hex
            conn.execute("INSERT INTO conversations (id, client_id, created_at) VALUES (?,?,?)", (new_id, client_id, self._now()))
            return new_id

    def add_message(self, conversation_id: str, role: str, content: str, payload: dict | None = None) -> int:
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO messages (conversation_id, role, content, payload, created_at) VALUES (?,?,?,?,?)",
                (conversation_id, role, content, json.dumps(payload) if payload else None, self._now()),
            )
            return int(cur.lastrowid)

    def recent_user_messages(self, conversation_id: str, limit: int = 4) -> list[str]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT content FROM messages WHERE conversation_id = ? AND role = 'user' ORDER BY id DESC LIMIT ?",
                (conversation_id, limit),
            ).fetchall()
        return [r["content"] for r in reversed(rows)]

    def message_client(self, message_id: int) -> str | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT c.client_id FROM messages m JOIN conversations c ON c.id = m.conversation_id WHERE m.id = ?",
                (message_id,),
            ).fetchone()
        return row["client_id"] if row else None

    def save_feedback(self, message_id: int, rating: str, comment: str | None) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO feedback (message_id, rating, comment, created_at) VALUES (?,?,?,?) "
                "ON CONFLICT(message_id) DO UPDATE SET rating = excluded.rating, comment = excluded.comment",
                (message_id, rating, comment, self._now()),
            )
