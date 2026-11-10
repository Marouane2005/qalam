import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import redis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from qalam import __version__
from qalam.auth import bootstrap_account
from qalam.config import Settings, get_settings
from qalam.db import session_factory
from qalam.errors import AppError
from qalam.llm.client import build_client
from qalam.llm.types import LLMUnavailable
from qalam.logging import configure_logging, get_logger
from qalam.metrics import HTTP_LATENCY, HTTP_REQUESTS
from qalam.migrate import migrate_with_retry
from qalam.routes import documents, guest, meta, reading, workspaces

log = get_logger("qalam.api")


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Any:
        import structlog

        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers["X-Request-ID"] = request_id
        route = request.scope.get("route")
        path = getattr(route, "path", "unmatched")
        HTTP_REQUESTS.labels(request.method, path, str(response.status_code)).inc()
        HTTP_LATENCY.labels(path).observe(time.perf_counter() - started)
        return response


def create_app(settings: Settings | None = None, redis_client: Any = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        migrate_with_retry(settings.database_url)
        app.state.session_factory = session_factory(settings)
        if app.state.redis is None:
            app.state.redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        app.state.llm = build_client(settings)
        log.info("llm_ready", providers=app.state.llm.provider_names)
        with app.state.session_factory() as session:
            bootstrap_account(
                session,
                email=settings.bootstrap_email,
                name=settings.bootstrap_name,
                workspace_name=settings.bootstrap_workspace,
                api_key=settings.bootstrap_api_key,
            )
            if settings.seed_demo:
                from qalam.seed import seed_if_empty

                seed_if_empty(session, settings, app.state.llm)
        yield
        try:
            app.state.redis.close()
        except Exception:
            pass

    app = FastAPI(
        title="Qalam",
        version=__version__,
        summary="Document intelligence for Arabic, French and English.",
        description=(
            "Upload a PDF, scan, Word file or plain text. Qalam extracts the text, "
            "detects the language, and can summarize, translate, answer questions "
            "with page citations, or fill a JSON schema."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.redis = redis_client
    app.state.llm = None
    app.state.session_factory = None
    app.add_middleware(RequestLogMiddleware)
    if settings.cors_origin_list():
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list(),
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(meta.router)
    app.include_router(workspaces.router)
    app.include_router(guest.router)
    app.include_router(documents.router)
    app.include_router(reading.router)

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content={"detail": {"code": exc.code, "message": exc.message}},
            headers=exc.headers,
        )

    @app.exception_handler(LLMUnavailable)
    async def handle_llm(_request: Request, _exc: LLMUnavailable) -> JSONResponse:
        log.warning("llm_unavailable")
        return JSONResponse(
            status_code=503,
            content={
                "detail": {
                    "code": "llm_unavailable",
                    "message": "No language model provider accepted the request.",
                }
            },
        )

    return app


app = create_app()
