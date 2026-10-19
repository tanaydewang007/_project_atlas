import re

from src.services.llm import LLMService


class SqlPlanner:
    TEMPLATES = [
        (r"how many sectors|number of sectors|count of sectors", "SELECT COUNT(DISTINCT sector) AS sector_count FROM reports"),
        (r"how many reports|number of reports|count of reports", "SELECT COUNT(*) AS report_count FROM reports"),
        (
            r"(sector|sectors).*(most|largest|highest|top)|most reports",
            "SELECT sector, COUNT(*) AS report_count FROM reports GROUP BY sector ORDER BY report_count DESC, sector",
        ),
        (
            r"publishers?.*(most|how many|list|which)|(which|list).*publishers?",
            "SELECT publisher, COUNT(*) AS report_count FROM reports GROUP BY publisher ORDER BY report_count DESC, publisher",
        ),
        (r"(latest|newest|most recent).*report", "SELECT id, title, published FROM reports ORDER BY published DESC LIMIT 1"),
        (r"(oldest|earliest).*report", "SELECT id, title, published FROM reports ORDER BY published ASC LIMIT 1"),
        (
            r"(list|show|which|what).*(reports|library)|reports.*(available|library)",
            "SELECT id, title, sector, published FROM reports ORDER BY published DESC",
        ),
    ]
    AGG_WORDS = re.compile(r"how many|count|number of|average|total|most|least|highest|lowest", re.I)
    TABLE_WORDS = re.compile(r"reports?|sectors?|publishers?|library|metrics?", re.I)
    SYSTEM = (
        "You write one read-only SQLite SELECT query. Tables: "
        "reports(id, title, publisher, published, sector, access); "
        "market_metrics(report, metric, region, period, value, unit, scope_note, page). "
        "Return only the SQL, no prose, no markdown."
    )

    def __init__(self, llm: LLMService) -> None:
        self.llm = llm
        self._compiled = [(re.compile(p, re.I), sql) for p, sql in self.TEMPLATES]

    METADATA = re.compile(
        r"\b(when|which year|what year|what date|who|which publisher|publisher)\b.{0,50}\b(publish|releas)|publish(ed)?[ -](date|year)|date of publication|publisher of",
        re.I,
    )

    def template(self, question: str) -> str | None:
        if self.METADATA.search(question):
            found = re.search(r"\bR-?(\d{3,4})\b", question, re.I)
            where = f" WHERE id = 'R-{found.group(1)}'" if found else ""
            return f"SELECT id, title, publisher, published FROM reports{where} ORDER BY published DESC"
        return next((sql for pattern, sql in self._compiled if pattern.search(question)), None)

    def looks_aggregate(self, question: str) -> bool:
        if self.template(question):
            return True
        return self.llm.enabled and bool(self.AGG_WORDS.search(question) and self.TABLE_WORDS.search(question))
