from __future__ import annotations

import uuid
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from context_engine.api.errors import (
    ApiError,
    api_error_handler,
    http_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from context_engine.api.contract_app import (
    API_TITLE,
    API_VERSION,
    CANONICAL_REQUEST_ID_HEADER,
    register_contract_routes,
)
from context_engine.config import Settings
from context_engine.db import create_db_engine, create_session_factory
from context_engine.services.audit import AuditError
from context_engine.services.auth import seed_admin
from context_engine.services.prompt_templates import seed_prompt_templates
from context_engine.services.runtime_config import seed_runtime_config, validate_config_encryption_key
from context_engine.services.structured_logging import configure_json_logging, safe_log

import logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings.from_env()
    configure_json_logging()
    validate_config_encryption_key(app_settings)
    engine = create_db_engine(app_settings)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = app_settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        db = session_factory()
        try:
            seed_admin(db, app_settings)
            seed_runtime_config(db)
            seed_prompt_templates(db)
        finally:
            db.close()
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title=API_TITLE, version=API_VERSION, lifespan=lifespan)
    app.state.settings = app_settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        started = time.perf_counter()
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.actor_kind = "public"
        try:
            response = await call_next(request)
        except Exception:
            safe_log(
                logger,
                "http_request",
                request_id=request_id,
                actor_kind=getattr(request.state, "actor_kind", "public"),
                elapsed_ms=int((time.perf_counter() - started) * 1000),
                http_method=request.method,
                http_route=_route_template(request),
                http_status=500,
                outcome="failed",
                safe_error_code="internal_error",
            )
            raise
        response.headers[CANONICAL_REQUEST_ID_HEADER] = request_id
        safe_log(
            logger,
            "http_request",
            request_id=request_id,
            actor_kind=getattr(request.state, "actor_kind", "public"),
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            http_method=request.method,
            http_route=_route_template(request),
            http_status=response.status_code,
            outcome="failed" if response.status_code >= 400 else "succeeded",
        )
        return response

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(AuditError, audit_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    register_contract_routes(app)
    return app


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else "unmatched"


async def audit_error_handler(request: Request, exc: AuditError):
    from context_engine.api.errors import error_response

    return error_response(request, exc.status_code, exc.code, exc.message)
