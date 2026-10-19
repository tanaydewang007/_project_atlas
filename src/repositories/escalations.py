from datetime import datetime, timezone

from src.db.database import Database
from src.models.schemas import EscalationOut


class EscalationRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, client_id: str, question: str, reason: str, confidence: float) -> int:
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO escalations (client_id, question, reason, confidence, created_at) VALUES (?,?,?,?,?)",
                (client_id, question, reason, confidence, datetime.now(timezone.utc).isoformat()),
            )
            return int(cur.lastrowid)

    def list(self, status: str | None = None, limit: int = 100) -> list[EscalationOut]:
        query = "SELECT * FROM escalations"
        args: list = []
        if status:
            query += " WHERE status = ?"
            args.append(status)
        query += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self.db.connect() as conn:
            rows = conn.execute(query, args).fetchall()
        return [EscalationOut(**dict(row)) for row in rows]
