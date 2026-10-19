import pytest
from fastapi.testclient import TestClient

from src.core.config import Settings
from src.main import create_app


@pytest.fixture(scope="module")
def open_client(tmp_path_factory):
    root = tmp_path_factory.mktemp("open")
    settings = Settings(db_path=str(root / "a.db"), chroma_path=":memory:", embedding_backend="hash", _env_file=None)
    with TestClient(create_app(settings)) as c:
        yield c


def test_no_keys_means_no_auth(open_client):
    health = open_client.get("/health").json()
    assert health["auth_required"] is False
    r = open_client.post("/chat", json={"client_id": "C-01", "message": "How many reports are in the library?"})
    assert r.status_code == 200 and "report_count=6" in r.json()["answer"]
    assert open_client.get("/admin/reports").status_code == 200
    assert open_client.get("/escalations").status_code == 200


def test_entitlements_still_apply_without_keys(open_client):
    r = open_client.post("/chat", json={"client_id": "C-02", "message": "What is the 2024 global market size in R-101?"}).json()
    assert "4.21" not in r["answer"] and "entitlement_denied" in r["flags"]


def test_unknown_client_is_404(open_client):
    resp = open_client.post("/chat", json={"client_id": "C-99", "message": "hello market"})
    assert resp.status_code == 404
