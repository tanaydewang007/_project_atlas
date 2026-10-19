import re
import sqlite3
import time
from dataclasses import dataclass

from src.core.config import Settings
from src.core.errors import SqlRejected
from src.db.schema import SANDBOX_SCHEMA
from src.repositories.reports import ReportRepository
from src.services.entitlement import EntitlementService


@dataclass
class SqlResult:
    query: str
    columns: list[str]
    rows: list[list]
    truncated: bool


class SqlToolService:
    BLOCKED = re.compile(
        r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|replace|vacuum|reindex|truncate|grant|revoke|load_extension|sqlite_master|sqlite_schema)\b",
        re.I,
    )
    ALLOWED_TABLES = {"reports", "market_metrics"}
    MAX_QUERY_CHARS = 1000

    def __init__(self, settings: Settings, reports: ReportRepository, entitlement: EntitlementService) -> None:
        self.row_limit = settings.sql_row_limit
        self.timeout_s = settings.sql_timeout_s
        self.reports = reports
        self.entitlement = entitlement

    def validate(self, sql: str) -> str:
        cleaned = sql.strip().rstrip(";").strip()
        if not cleaned or len(cleaned) > self.MAX_QUERY_CHARS:
            raise SqlRejected("empty or oversized query")
        if ";" in cleaned:
            raise SqlRejected("multiple statements are not allowed")
        if not re.match(r"^(select|with)\b", cleaned, re.I):
            raise SqlRejected("only SELECT queries are allowed")
        if self.BLOCKED.search(cleaned):
            raise SqlRejected("query contains a blocked keyword")
        return cleaned

    def _sandbox(self, client_id: str) -> sqlite3.Connection:
        entitled = self.entitlement.entitled_ids(client_id)
        conn = sqlite3.connect(":memory:")
        conn.executescript(SANDBOX_SCHEMA)
        conn.executemany(
            "INSERT INTO reports VALUES (?,?,?,?,?,?)",
            [(r.id, r.title, r.publisher, r.published, r.sector, r.access) for r in self.reports.all()],
        )
        conn.executemany(
            "INSERT INTO market_metrics VALUES (?,?,?,?,?,?,?,?)",
            [(m.report_id, m.metric, m.region, m.period, m.value, m.unit, m.scope_note, m.page) for m in self.reports.metrics(entitled)],
        )
        conn.commit()
        conn.execute("PRAGMA query_only=ON")
        conn.set_authorizer(self._authorize)
        return conn

    def _authorize(self, action, arg1, arg2, dbname, source) -> int:
        if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE, sqlite3.SQLITE_FUNCTION):
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ and arg1 in self.ALLOWED_TABLES:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    def run(self, client_id: str, sql: str) -> SqlResult:
        query = self.validate(sql)
        conn = self._sandbox(client_id)
        deadline = time.monotonic() + self.timeout_s
        conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 1000)
        try:
            cur = conn.execute(query)
            rows = cur.fetchmany(self.row_limit + 1)
            columns = [d[0] for d in cur.description or []]
        except sqlite3.Error as exc:
            raise SqlRejected(str(exc)) from exc
        finally:
            conn.close()
        return SqlResult(query, columns, [list(r) for r in rows[: self.row_limit]], len(rows) > self.row_limit)
