import io
import json

import pytest
from pypdf import PdfWriter

from src.db.database import Database
from src.db.seed import Seeder
from src.tests.conftest import ADMIN, C01, C02, ask

REPORT_TEXT = (
    "[[page 1]]\n## Summary\nThe global smart grid analytics market was valued at USD 5.5 billion in 2024 "
    "and is expected to grow at a CAGR of 8.0% from 2025 to 2030.\n"
)
FORM = {"title": "Smart Grid Analytics Market 2025", "publisher": "CMR", "published": "2025-05-01", "sector": "Energy"}
METRICS = [{"metric": "Market size", "region": "Global", "period": "2024", "value": 5.5, "scope_note": "Software and services", "page": 1}]


@pytest.fixture
def reports_dir(container, tmp_path):
    old = container.report_admin.dir, container.ingestion.dir
    container.report_admin.dir = container.ingestion.dir = tmp_path
    yield tmp_path
    container.report_admin.dir, container.ingestion.dir = old


def upload(client, name="r.md", content=REPORT_TEXT.encode(), data=None, headers=None):
    return client.post("/admin/reports", data={**FORM, **(data or {})}, files={"file": (name, io.BytesIO(content))}, headers=headers)


def test_admin_page_is_served(client):
    assert "Manage reports" in client.get("/admin").text


def test_upload_share_ask_and_delete(client, container, reports_dir):
    resp = upload(client, data={"client_ids": ["C-01"], "metrics": json.dumps(METRICS)})
    assert resp.status_code == 201, resp.text
    created = resp.json()
    rid = created["id"]
    assert created["chunks"] > 0 and created["client_ids"] == ["C-01"] and (reports_dir / f"{rid}.md").exists()

    r = ask(client, "C-01", "What is the smart grid analytics market size in 2024?", C01)
    assert "5.5" in r["answer"] and [c["report_id"] for c in r["citations"]] == [rid]
    assert ask(client, "C-01", "How is smart grid analytics adoption going?", C01)["intent"] != "out_of_scope"
    other = ask(client, "C-02", "What is the smart grid analytics market size in 2024?", C02)
    assert "5.5" not in other["answer"] and "entitlement_denied" in other["flags"]

    shared = client.put(f"/admin/reports/{rid}/access", json={"client_ids": ["C-01", "C-02"]}, headers=ADMIN).json()
    assert shared["client_ids"] == ["C-01", "C-02"]
    assert "5.5" in ask(client, "C-02", "What is the smart grid analytics market size in 2024?", C02)["answer"]

    assert client.delete(f"/admin/reports/{rid}", headers=ADMIN).status_code == 204
    assert not (reports_dir / f"{rid}.md").exists()
    gone = ask(client, "C-01", "What is the smart grid analytics market size in 2024?", C01)
    assert "5.5" not in gone["answer"]
    overview = client.get("/admin/reports", headers=ADMIN).json()
    assert rid not in [x["id"] for x in overview["reports"]]
    assert all(rid not in c.purchased for c in container.clients.all())
    assert container.store.report_chunk_count(rid) == 0


def test_plain_text_without_page_markers_is_paged(client, reports_dir):
    text = ("Smart grids need analytics. " * 40 + "\n\n") * 5
    resp = upload(client, name="notes.txt", content=text.encode(), data={"access": "public excerpt"})
    assert resp.status_code == 201 and resp.json()["chunks"] > 1
    client.delete(f"/admin/reports/{resp.json()['id']}", headers=ADMIN)


@pytest.mark.parametrize(
    "kwargs, status",
    [
        ({"name": "x.exe"}, 422),
        ({"content": b""}, 422),
        ({"content": b"\xff\xfe\x00bad"}, 422),
        ({"name": "x.pdf", "content": b"not a pdf"}, 422),
        ({"data": {"published": "yesterday"}}, 422),
        ({"data": {"access": "free"}}, 422),
        ({"data": {"client_ids": ["C-99"]}}, 422),
        ({"data": {"report_id": "R-101"}}, 409),
        ({"data": {"report_id": "../evil"}}, 422),
        ({"data": {"metrics": json.dumps([{"metric": "CAGR", "region": "Global", "period": "2024", "value": 5}])}}, 422),
        ({"data": {"metrics": "not json"}}, 422),
    ],
)
def test_bad_uploads_are_rejected_and_leave_nothing_behind(client, container, reports_dir, kwargs, status):
    before = [r.id for r in container.reports.all()]
    assert upload(client, **kwargs).status_code == status
    assert [r.id for r in container.reports.all()] == before
    assert list(reports_dir.iterdir()) == []


def test_pdf_without_text_is_rejected(client, container, reports_dir):
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(buffer)
    resp = upload(client, name="scan.pdf", content=buffer.getvalue())
    assert resp.status_code == 422 and "No readable text" in resp.json()["detail"]
    assert list(reports_dir.iterdir()) == []


def test_delete_unknown_report_and_public_access_rules(client):
    assert client.delete("/admin/reports/R-999", headers=ADMIN).status_code == 404
    assert client.put("/admin/reports/R-102/access", json={"client_ids": ["C-01"]}, headers=ADMIN).status_code == 422


def test_deleted_seed_report_does_not_come_back(tmp_path):
    db = Database(str(tmp_path / "seed.db"))
    db.init_schema()
    Seeder(db).run()
    with db.connect() as conn:
        conn.execute("DELETE FROM market_metrics WHERE report = 'R-104'")
        conn.execute("DELETE FROM reports WHERE id = 'R-104'")
    Seeder(db).run()
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM reports WHERE id = 'R-104'").fetchone()[0] == 0


def test_chunks_view_shows_stored_text_and_flags_the_trap(client):
    chunks = client.get("/admin/reports/R-102/chunks").json()
    assert [c["page"] for c in chunks] == sorted(c["page"] for c in chunks)
    flagged = [c for c in chunks if c["suspicious"]]
    assert flagged and all(c["page"] == 14 for c in flagged)
    assert not any(c["suspicious"] for c in client.get("/admin/reports/R-101/chunks").json())
    assert client.get("/admin/reports/R-999/chunks").status_code == 404
