import asyncio
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from src.api.deps import client_scope, get_container
from src.core.container import Container
from src.core.errors import AgentTimeout
from pydantic import ValidationError

from src.core.errors import AdminError
from src.models.schemas import (
    AccessUpdate,
    AdminOverview,
    ChatRequest,
    ChatResponse,
    ChunkOut,
    EscalationOut,
    FeedbackRequest,
    IngestRequest,
    IngestResult,
    ReportAdminOut,
    ReportCreate,
)

router = APIRouter()


@router.get("/health")
def health(container: Container = Depends(get_container)) -> dict:
    with container.db.connect() as conn:
        conn.execute("SELECT 1")
    return {
        "status": "ok",
        "vector_chunks": container.store.count(),
        "embedding_backend": container.embedder.backend,
        "llm_enabled": container.llm.enabled,
        "auth_required": bool(container.settings.api_key_map),
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, scope: str | None = Depends(client_scope), container: Container = Depends(get_container)) -> ChatResponse:
    if scope is not None and scope != body.client_id:
        raise HTTPException(status_code=403, detail="API key is not valid for this client")
    try:
        return await asyncio.wait_for(asyncio.to_thread(container.chat.handle, body), timeout=container.settings.request_timeout_s)
    except asyncio.TimeoutError as exc:
        raise AgentTimeout("request timed out") from exc


@router.post("/feedback", status_code=204)
def feedback(body: FeedbackRequest, scope: str | None = Depends(client_scope), container: Container = Depends(get_container)) -> None:
    owner = container.conversations.message_client(body.message_id)
    if owner is None or (scope is not None and scope != owner):
        raise HTTPException(status_code=404, detail="message not found")
    container.conversations.save_feedback(body.message_id, body.rating, body.comment)


@router.post("/ingest", response_model=IngestResult)
async def ingest(body: IngestRequest, container: Container = Depends(get_container)) -> IngestResult:
    return await asyncio.to_thread(container.ingestion.ingest, body.report_ids)


@router.get("/escalations", response_model=list[EscalationOut])
def escalations(status: str | None = None, container: Container = Depends(get_container)) -> list[EscalationOut]:
    return container.escalations.list(status)


@router.get("/", include_in_schema=False)
def ui() -> FileResponse:
    return FileResponse("src/web/index.html")


@router.get("/admin", include_in_schema=False)
def admin_page() -> FileResponse:
    return FileResponse("src/web/admin.html")


@router.get("/admin/reports", response_model=AdminOverview)
async def admin_reports(container: Container = Depends(get_container)) -> AdminOverview:
    return await asyncio.to_thread(container.report_admin.overview)


@router.post("/admin/reports", response_model=ReportAdminOut, status_code=201)
async def admin_create_report(
    title: str = Form(...),
    publisher: str = Form(...),
    published: str = Form(...),
    sector: str = Form(...),
    access: str = Form("paid"),
    report_id: str | None = Form(None),
    client_ids: list[str] = Form(default=[]),
    metrics: str = Form("[]"),
    file: UploadFile = File(...),
    container: Container = Depends(get_container),
) -> ReportAdminOut:
    try:
        meta = ReportCreate(
            id=report_id or None,
            title=title.strip(),
            publisher=publisher.strip(),
            published=published,
            sector=sector.strip(),
            access=access,
            client_ids=client_ids,
            metrics=json.loads(metrics or "[]"),
        )
    except (ValidationError, ValueError) as exc:
        raise AdminError(_readable(exc)) from exc
    content = await file.read(11 * 1024 * 1024)
    return await asyncio.to_thread(container.report_admin.create, meta, file.filename or "", content)


@router.get("/admin/reports/{report_id}/chunks", response_model=list[ChunkOut])
async def admin_report_chunks(report_id: str, container: Container = Depends(get_container)) -> list[ChunkOut]:
    return await asyncio.to_thread(container.report_admin.chunks, report_id)


@router.delete("/admin/reports/{report_id}", status_code=204)
async def admin_delete_report(report_id: str, container: Container = Depends(get_container)) -> None:
    await asyncio.to_thread(container.report_admin.delete, report_id)


@router.put("/admin/reports/{report_id}/access", response_model=ReportAdminOut)
async def admin_set_access(report_id: str, body: AccessUpdate, container: Container = Depends(get_container)) -> ReportAdminOut:
    return await asyncio.to_thread(container.report_admin.set_access, report_id, body.client_ids)


def _readable(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
    return f"Invalid input: {exc}"
