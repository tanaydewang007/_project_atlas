import logging
import re
from pathlib import Path

from src.core.config import Settings
from src.core.logging import log_event
from src.models.domain import Chunk
from src.models.schemas import IngestResult
from src.repositories.audit import AuditRepository
from src.repositories.reports import ReportRepository
from src.services.chunker import Chunker
from src.services.injection_guard import InjectionGuard
from src.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(
        self,
        settings: Settings,
        reports: ReportRepository,
        store: VectorStore,
        chunker: Chunker,
        guard: InjectionGuard,
        audit: AuditRepository,
    ) -> None:
        self.dir = Path(settings.reports_dir)
        self.reports = reports
        self.store = store
        self.chunker = chunker
        self.guard = guard
        self.audit = audit

    def _find(self, report_id: str) -> Path | None:
        return next((p for ext in (".md", ".txt", ".pdf") if (p := self.dir / f"{report_id}{ext}").is_file()), None)

    def ingest(self, report_ids: list[str] | None = None) -> IngestResult:
        done, skipped, total = [], {}, 0
        for report in self.reports.all():
            if report_ids is not None and report.id not in report_ids:
                continue
            path = self._find(report.id)
            if path is None:
                skipped[report.id] = "source file not found"
                continue
            chunks, metas = [], {}
            for page, text in self.chunker.load_pages(path):
                _, hits = self.guard.sanitize(text)
                for hit in hits:
                    self.audit.log_injection(None, "document_injection", f"{report.id} p.{page}", hit)
                    log_event(logger, "injection_detected", source=f"{report.id} p.{page}", stage="ingest")
                for i, part in enumerate(self.chunker.split(text)):
                    chunk = Chunk(f"{report.id}-p{page}-{i}", report.id, page, part)
                    chunks.append(chunk)
                    metas[chunk.id] = {
                        "sector": report.sector,
                        "access": report.access,
                        "year": int(report.published[:4]),
                        "region": "APAC" if re.search(r"asia-pacific|apac", part, re.I) else "Global",
                    }
            self.store.delete_report(report.id)
            self.store.upsert(chunks, metas)
            done.append(report.id)
            total += len(chunks)
        return IngestResult(reports_ingested=done, chunks=total, skipped=skipped)
