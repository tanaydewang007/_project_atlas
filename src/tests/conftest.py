import logging

import pytest
from fastapi.testclient import TestClient

from src.core.config import Settings
from src.core.container import Container
from src.main import create_app

logging.disable(logging.CRITICAL)

ADMIN: dict = {}
C01 = {"X-API-Key": "demo-c01"}
C02 = {"X-API-Key": "demo-c02"}


@pytest.fixture(scope="session")
def settings(tmp_path_factory) -> Settings:
    root = tmp_path_factory.mktemp("atlas")
    return Settings(
        db_path=str(root / "atlas.db"),
        chroma_path=":memory:",
        embedding_backend="hash",
        api_keys="demo-c01:C-01,demo-c02:C-02",
        _env_file=None,
    )


@pytest.fixture(scope="session")
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture(scope="session")
def container(client) -> Container:
    return client.app.state.container


def ask(client, client_id: str, message: str, headers: dict) -> dict:
    resp = client.post("/chat", json={"client_id": client_id, "message": message}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()
