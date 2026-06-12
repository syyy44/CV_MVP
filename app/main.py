from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.logging import get_logger
from app.locale import zh_CN as msg
from app.storage.db import init_db

log = get_logger(__name__)

# Built React SPA (frontend/dist). Served at "/" in production; in dev the Vite
# server proxies /api and /health to this app instead.
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    settings = get_settings()
    log.info(
        "recruiting assistant up: mode=%s model=%s langfuse=%s",
        settings.demo_mode,
        settings.model_name,
        "on" if settings.langfuse_configured else "local-fallback",
    )
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="智能招聘助手",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(router)

    @app.exception_handler(DomainError)
    async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled API error")
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": msg.unexpected_server_error()}},
        )

    # Mount the built SPA last so API routes keep priority. html=True serves
    # index.html at "/" and falls back to it for client-side paths.
    if FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="spa")
    else:
        log.info(
            "frontend build not found at %s — run 'make ui-build' (dev uses Vite)",
            FRONTEND_DIST,
        )

    return app


app = create_app()
