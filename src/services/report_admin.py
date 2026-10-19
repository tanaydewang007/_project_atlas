import logging
from pathlib import Path

from src.core.config import Settings
from src.core.errors import AdminError
from src.core.logging import log_event
from src.models.domain import Metric, Report
from src.models.schemas import AdminOverview, ChunkOut, ClientBrief, MetricOut, ReportAdminOut, ReportCreate
from src.repositories.cache import CacheRepository
from src.repositories.clients import ClientRepository
from src.repositories.reports import ReportRepository
from src.services.ingestion import IngestionService
from src.services.injection_guard import InjectionGuard
from src.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".md", ".txt", ".pdf"}
MAX_BYTES = 10 * 1024 * 1024


class ReportAdminService:
    def __init__(
        self,
        settings: Settings,
        reports: ReportRepository,
        clients: ClientRepository,
        store: VectorStore,
        ingestion: IngestionService,
        cache: CacheRepository,
        guard: InjectionGuard,
    ) -> None:
        self.dir = Path(settings.reports_dir)
        self.reports = reports
        self.clients = clients
        self.store = store
        self.ingestion = ingestion
        self.cache = cache
        self.guard = guard

    def overview(self) -> AdminOverview:
        clients = self.clients.all()
        metrics = self.reports.metrics()
        return AdminOverview(
            reports=[self._out(r, clients, metrics) for r in self.reports.all()],
            clients=[ClientBrief(id=c.id, company=c.company) for c in clients],
        )

    def create(self, meta: ReportCreate, filename: str, content: bytes) -> ReportAdminOut:
        extension = Path(filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise AdminError("Upload a .md, .txt or .pdf file.")
        if not content or len(content) > MAX_BYTES:
            raise AdminError("The file is empty or larger than 10 MB.")
        if extension != ".pdf":
            try:
                if not content.decode("utf-8").strip():
                    raise AdminError("The file has no text.")
            except UnicodeDecodeError as exc:
                raise AdminError("Text files must be UTF-8 encoded.") from exc
        known = {c.id for c in self.clients.all()}
        unknown = [c for c in meta.client_ids if c not in known]
        if unknown:
            raise AdminError(f"Unknown client(s): {', '.join(unknown)}")
        keys = [(m.metric, m.region, m.period) for m in meta.metrics]
        if len(keys) != len(set(keys)):
            raise AdminError("The same figure (metric, region, period) is listed twice.")
        report_id = meta.id or self.reports.next_id()
        if self.reports.get(report_id):
            raise AdminError(f"Report {report_id} already exists. Delete it first or use another id.", 409)

        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / f"{report_id}{extension}").write_bytes(content)
        try:
            self.reports.insert(Report(report_id, meta.title, meta.publisher, meta.published, meta.sector, meta.access))
            self.reports.insert_metrics(
                [Metric(report_id, m.metric, m.region, m.period, m.value, m.unit, m.scope_note or "As stated in the report", m.page) for m in meta.metrics]
            )
            if meta.access == "paid" and meta.client_ids:
                self.clients.set_access(report_id, meta.client_ids)
            result = self.ingestion.ingest([report_id])
            if not result.chunks:
                raise AdminError("No readable text was found in the file (scanned PDFs are not supported).")
        except AdminError:
            self._remove(report_id)
            raise
        except Exception as exc:
            logger.exception("report ingest failed")
            self._remove(report_id)
            raise AdminError("The file could not be read. Check that it is a valid document.") from exc
        self.cache.clear()
        log_event(logger, "report_added", report_id=report_id, chunks=result.chunks)
        return self._single(report_id)

    def chunks(self, report_id: str) -> list[ChunkOut]:
        if not self.reports.get(report_id):
            raise AdminError("Report not found.", 404)
        return [
            ChunkOut(id=c.id, page=c.page, text=c.text, suspicious=bool(self.guard.sanitize(c.text)[1]))
            for c in self.store.report_chunks(report_id)
        ]

    def delete(self, report_id: str) -> None:
        if not self.reports.get(report_id):
            raise AdminError("Report not found.", 404)
        self._remove(report_id)
        log_event(logger, "report_deleted", report_id=report_id)

    def set_access(self, report_id: str, client_ids: list[str]) -> ReportAdminOut:
        report = self.reports.get(report_id)
        if not report:
            raise AdminError("Report not found.", 404)
        if report.is_public:
            raise AdminError("A public excerpt is visible to every client.")
        known = {c.id for c in self.clients.all()}
        if any(c not in known for c in client_ids):
            raise AdminError("Unknown client in the list.")
        self.clients.set_access(report_id, client_ids)
        self.cache.clear()
        return self._single(report_id)

    def _remove(self, report_id: str) -> None:
        self.store.delete_report(report_id)
        self.reports.delete(report_id)
        self.clients.set_access(report_id, [])
        for extension in ALLOWED_EXTENSIONS:
            (self.dir / f"{report_id}{extension}").unlink(missing_ok=True)
        self.cache.clear()

    def _single(self, report_id: str) -> ReportAdminOut:
        return next(r for r in self.overview().reports if r.id == report_id)

    def _out(self, report: Report, clients: list, metrics: list[Metric]) -> ReportAdminOut:
        source = next((p.name for e in (".md", ".txt", ".pdf") if (p := self.dir / f"{report.id}{e}").is_file()), None)
        return ReportAdminOut(
            id=report.id,
            title=report.title,
            publisher=report.publisher,
            published=report.published,
            sector=report.sector,
            access=report.access,
            chunks=self.store.report_chunk_count(report.id),
            source_file=source,
            client_ids=[c.id for c in clients if report.id in c.purchased],
            metrics=[
                MetricOut(metric=m.metric, region=m.region, period=m.period, value=m.value, unit=m.unit, scope_note=m.scope_note, page=m.page)
                for m in metrics
                if m.report_id == report.id
            ],
        )
