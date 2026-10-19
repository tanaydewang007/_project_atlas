from src.db.database import Database
from src.models.domain import Client


class ClientRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def all(self) -> list[Client]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM clients ORDER BY id").fetchall()
        return [
            Client(r["id"], r["company"], r["contact_email"], tuple(p.strip() for p in r["purchased_reports"].split(",") if p.strip()))
            for r in rows
        ]

    def get(self, client_id: str) -> Client | None:
        return next((c for c in self.all() if c.id == client_id), None)

    def set_access(self, report_id: str, client_ids: list[str]) -> None:
        with self.db.connect() as conn:
            for client in self.all():
                owned = set(client.purchased)
                owned = owned | {report_id} if client.id in client_ids else owned - {report_id}
                conn.execute("UPDATE clients SET purchased_reports = ? WHERE id = ?", (", ".join(sorted(owned)), client.id))
