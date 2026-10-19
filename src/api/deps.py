import hmac

from fastapi import Depends, Header, HTTPException, Request

from src.core.container import Container


def get_container(request: Request) -> Container:
    return request.app.state.container


def _match(key: str | None, candidates: dict[str, str | None]) -> tuple[bool, str | None]:
    if not key:
        return False, None
    for known, client in candidates.items():
        if known and hmac.compare_digest(key.encode(), known.encode()):
            return True, client
    return False, None


def client_scope(
    x_api_key: str | None = Header(default=None), container: Container = Depends(get_container)
) -> str | None:
    settings = container.settings
    if not settings.api_key_map:
        return None
    ok, client = _match(x_api_key, settings.api_key_map)
    if not ok:
        raise HTTPException(status_code=401, detail="invalid or missing API key")
    return client
