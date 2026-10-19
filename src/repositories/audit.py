from datetime import datetime, timezone

from src.db.database import Database


class AuditRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def log_injection(self, client_id: str | None, kind: str, source: str, detail: str) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO injection_log (client_id, kind, source, detail, created_at) VALUES (?,?,?,?,?)",
                (client_id, kind, source, detail[:500], self._now()),
            )

    def log_usage(self, client_id: str, intent: str, tokens_in: int, tokens_out: int, cost: float, latency_ms: int, cached: bool) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO usage_log (client_id, intent, input_tokens, output_tokens, cost_usd, latency_ms, cached, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (client_id, intent, tokens_in, tokens_out, cost, latency_ms, int(cached), self._now()),
            )
