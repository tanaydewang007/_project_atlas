import re

from src.models.domain import Chunk, Metric
from src.models.schemas import Citation
from src.repositories.reports import ReportRepository
from src.services.injection_guard import InjectionGuard
from src.services.vector_store import VectorStore


class CitationService:
    def __init__(self, store: VectorStore, reports: ReportRepository, guard: InjectionGuard) -> None:
        self.store = store
        self.reports = reports
        self.guard = guard
        self._titles: dict[str, str] = {}

    def title(self, report_id: str) -> str:
        if report_id not in self._titles:
            self._titles = {r.id: r.title for r in self.reports.all()}
        return self._titles.get(report_id, report_id)

    def for_metric(self, metric: Metric) -> Citation:
        text = " ".join(c.text for c in self.store.page_chunks(metric.report_id, metric.page or 0))
        clean, _ = self.guard.sanitize(text)
        needle = f"{metric.value:g}"
        sentence = next((s for s in re.split(r"(?<=[.!?])\s+", clean) if needle in s), None)
        snippet = sentence or clean[:240] or f"{metric.metric}: {metric.display} ({metric.scope_note})"
        return Citation(report_id=metric.report_id, title=self.title(metric.report_id), page=metric.page, snippet=snippet[:300])

    def for_chunk(self, chunk: Chunk) -> Citation:
        return Citation(report_id=chunk.report_id, title=self.title(chunk.report_id), page=chunk.page, snippet=chunk.text[:300])
