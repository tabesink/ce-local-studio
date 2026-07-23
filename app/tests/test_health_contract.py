from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from context_engine.api.contract_app import (
    CANONICAL_API_PREFIX,
    CANONICAL_REQUEST_ID_HEADER,
    register_contract_routes,
)
from context_engine.api.dependencies import get_db
from context_engine.api.public_schemas import APPROVED_HTTP_ERROR_CODES
from context_engine.api.routes import live, ready
from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base


class HealthyDatabase:
    def execute(self, _statement: object) -> None:
        return None


class UnhealthyDatabase:
    def execute(self, _statement: object) -> None:
        raise RuntimeError("private database failure")


def test_health_handlers_return_catalog_statuses() -> None:
    assert live() == {"status": "live"}
    assert ready(HealthyDatabase()) == {"status": "ready"}


def test_health_openapi_uses_closed_response_schemas() -> None:
    app = FastAPI()
    register_contract_routes(app)
    document = app.openapi()

    live_response = document["paths"]["/health/live"]["get"]["responses"]["200"]
    ready_responses = document["paths"]["/health/ready"]["get"]["responses"]

    assert live_response["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/LiveHealthResponse"
    }
    assert ready_responses["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ReadyHealthResponse"
    }
    assert ready_responses["503"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorEnvelope"
    }
    assert set(document["components"]["schemas"]["ErrorDetail"]["required"]) == {
        "code",
        "message",
        "requestId",
        "fields",
    }
    error_codes = document["components"]["schemas"]["ErrorDetail"]["properties"]["code"]["enum"]
    assert set(error_codes) == set(APPROVED_HTTP_ERROR_CODES)
    assert CANONICAL_API_PREFIX == "/api/v1"


def test_readiness_failure_returns_closed_safe_error_envelope(tmp_path: Path) -> None:
    database_path = tmp_path / "health.db"
    settings = Settings(database_url=f"sqlite+pysqlite:///{database_path}", testing=True)
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    app.dependency_overrides[get_db] = lambda: UnhealthyDatabase()

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "dependency_unavailable",
            "message": "Service unavailable.",
            "requestId": response.headers[CANONICAL_REQUEST_ID_HEADER],
            "fields": {},
        }
    }
    assert response.headers[CANONICAL_REQUEST_ID_HEADER]

