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
    error_response,
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
from context_engine.services.prompt_templates import seed_prompt_templates
from context_engine.services.runtime_config import seed_runtime_config, validate_config_encryption_key
from context_engine.services.structured_logging import configure_json_logging, safe_log
from context_engine.services.metrics import safe_increment, status_class_for
from context_engine.services.request_security import RequestSecurityError, build_request_security_policy, enforce_request_security

import logging

logger = logging.getLogger(__name__)


def _emit_http_metric(
    *,
    method: str,
    route: str,
    status_code: int,
    outcome: str,
    actor_kind: str,
    safe_error_code: str | None = None,
) -> None:
    try:
        labels: dict[str, object] = {
            "http_method": method,
            "http_route": route,
            "outcome": outcome,
            "actor_kind": actor_kind,
            "status_class": status_class_for(status_code),
        }
        if safe_error_code:
            labels["safe_error_code"] = safe_error_code
        safe_increment("http_request", **labels)
    except Exception:
        # Metrics must never prevent returning the HTTP response.
        pass


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings.from_env()
    configure_json_logging()
    validate_config_encryption_key(app_settings)
    request_security_policy = build_request_security_policy(app_settings)
    engine = create_db_engine(app_settings)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = app_settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        db = session_factory()
        try:
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
            enforce_request_security(request, app_settings, request_security_policy)
        except RequestSecurityError as exc:
            response = error_response(request, exc.status_code, exc.code, exc.message)
            response.headers[CANONICAL_REQUEST_ID_HEADER] = request_id
            route = _route_template(request)
            safe_log(
                logger,
                "http_request",
                request_id=request_id,
                actor_kind="public",
                elapsed_ms=int((time.perf_counter() - started) * 1000),
                http_method=request.method,
                http_route=route,
                http_status=exc.status_code,
                outcome="failed",
                safe_error_code=exc.code,
            )
            _emit_http_metric(
                method=request.method,
                route=route,
                status_code=exc.status_code,
                outcome="failed",
                actor_kind="public",
                safe_error_code=exc.code,
            )
            return response
        try:
            response = await call_next(request)
        except Exception:
            route = _route_template(request)
            safe_log(
                logger,
                "http_request",
                request_id=request_id,
                actor_kind=getattr(request.state, "actor_kind", "public"),
                elapsed_ms=int((time.perf_counter() - started) * 1000),
                http_method=request.method,
                http_route=route,
                http_status=500,
                outcome="failed",
                safe_error_code="internal_error",
            )
            _emit_http_metric(
                method=request.method,
                route=route,
                status_code=500,
                outcome="failed",
                actor_kind=getattr(request.state, "actor_kind", "public"),
                safe_error_code="internal_error",
            )
            raise
        response.headers[CANONICAL_REQUEST_ID_HEADER] = request_id
        route = _route_template(request)
        outcome = "failed" if response.status_code >= 400 else "succeeded"
        actor_kind = getattr(request.state, "actor_kind", "public")
        safe_log(
            logger,
            "http_request",
            request_id=request_id,
            actor_kind=actor_kind,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            http_method=request.method,
            http_route=route,
            http_status=response.status_code,
            outcome=outcome,
        )
        _emit_http_metric(
            method=request.method,
            route=route,
            status_code=response.status_code,
            outcome=outcome,
            actor_kind=actor_kind,
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
    return error_response(request, exc.status_code, exc.code, exc.message)
