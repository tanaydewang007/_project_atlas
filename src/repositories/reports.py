from src.db.database import Database
from src.models.domain import Metric, Report


class ReportRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def all(self) -> list[Report]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM reports ORDER BY id").fetchall()
        return [Report(**dict(row)) for row in rows]

    def get(self, report_id: str) -> Report | None:
        return next((r for r in self.all() if r.id == report_id), None)

    def metrics(self, report_ids: list[str] | None = None) -> list[Metric]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM market_metrics ORDER BY report, id").fetchall()
        metrics = [
            Metric(r["report"], r["metric"], r["region"], r["period"], r["value"], r["unit"], r["scope_note"], r["page"])
            for r in rows
        ]
        return metrics if report_ids is None else [m for m in metrics if m.report_id in report_ids]

    def next_id(self) -> str:
        numbers = [int(r.id[2:]) for r in self.all() if r.id[2:].isdigit()]
        return f"R-{max(numbers, default=100) + 1:03d}"

    def insert(self, report: Report) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO reports VALUES (?,?,?,?,?,?)",
                (report.id, report.title, report.publisher, report.published, report.sector, report.access),
            )

    def insert_metrics(self, metrics: list[Metric]) -> None:
        with self.db.connect() as conn:
            conn.executemany(
                "INSERT INTO market_metrics (report, metric, region, period, value, unit, scope_note, page) VALUES (?,?,?,?,?,?,?,?)",
                [(m.report_id, m.metric, m.region, m.period, m.value, m.unit, m.scope_note, m.page) for m in metrics],
            )

    def delete(self, report_id: str) -> None:
        with self.db.connect() as conn:
            conn.execute("DELETE FROM market_metrics WHERE report = ?", (report_id,))
            conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
