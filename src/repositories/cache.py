import time

from src.db.database import Database


class CacheRepository:
    def __init__(self, db: Database, ttl_s: int) -> None:
        self.db = db
        self.ttl_s = ttl_s

    def get(self, key: str) -> str | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT response, created_at FROM answer_cache WHERE key = ?", (key,)).fetchone()
        if row and time.time() - row["created_at"] < self.ttl_s:
            return row["response"]
        return None

    def clear(self) -> None:
        with self.db.connect() as conn:
            conn.execute("DELETE FROM answer_cache")

    def put(self, key: str, response: str) -> None:
        with self.db.connect() as conn:
            conn.execute("INSERT OR REPLACE INTO answer_cache (key, response, created_at) VALUES (?,?,?)", (key, response, time.time()))
