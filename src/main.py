from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.routes import router
from src.core.config import Settings, get_settings
from src.core.container import Container
from src.core.errors import AdminError, AgentTimeout, ClientNotFound
from src.core.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.container = Container(settings)
        app.state.container.startup()
        yield

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(router)

    @app.exception_handler(ClientNotFound)
    async def client_not_found(_: Request, exc: ClientNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "unknown client"})

    @app.exception_handler(AgentTimeout)
    async def timeout(_: Request, exc: AgentTimeout) -> JSONResponse:
        return JSONResponse(
            status_code=504,
            content={"detail": "The assistant took too long to answer. Please try again, or ask for an analyst."},
        )

    @app.exception_handler(AdminError)
    async def admin_error(_: Request, exc: AdminError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    return app


app = create_app()
