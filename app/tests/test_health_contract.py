from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

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
from context_engine.models import DOMAIN_STATE_STOPPED, ROLE_ADMINISTRATOR, Domain, ProviderConfig
from context_engine.services.auth import create_user
from context_engine.adapters.object_storage import ObjectStorageError
from context_engine.services import readiness as readiness_module
from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD, ReadinessError, check_readiness
from context_engine.services.runtime_config import is_provider_configured, seed_runtime_config


class HealthyDatabase:
    def execute(self, _statement: object) -> None:
        return None

    def scalar(self, statement: object) -> str:
        if "alembic_version" in str(statement):
            return SUPPORTED_ALEMBIC_HEAD
        return "enabled-administrator-id"


class UnhealthyDatabase:
    def execute(self, _statement: object) -> None:
        raise RuntimeError("private database failure")


class _RevisionDatabase:
    def __init__(self, revision: object) -> None:
        self._revision = revision

    def execute(self, _statement: object) -> None:
        return None

    def scalar(self, statement: object) -> object:
        if "alembic_version" in str(statement):
            return self._revision
        return "enabled-administrator-id"


class NoAdministratorDatabase(HealthyDatabase):
    def scalar(self, statement: object) -> object:
        if "alembic_version" in str(statement):
            return SUPPORTED_ALEMBIC_HEAD
        return None


def test_health_handlers_return_catalog_statuses(tmp_path: Path) -> None:
    settings = Settings(testing=True, source_storage_root=str(tmp_path / "source-storage"))
    assert live() == {"status": "live"}
    assert ready(HealthyDatabase(), settings) == {"status": "ready"}


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
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        testing=True,
        source_storage_root=str(tmp_path / "source-storage"),
    )
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
    assert response.headers["Cache-Control"] == "private, no-store, no-transform"


def test_live_stays_ok_when_ready_dependencies_fail(tmp_path: Path) -> None:
    database_path = tmp_path / "health-live.db"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        testing=True,
        source_storage_root=str(tmp_path / "source-storage"),
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    app.dependency_overrides[get_db] = lambda: UnhealthyDatabase()

    with TestClient(app) as client:
        live_response = client.get("/health/live")
        ready_response = client.get("/health/ready")

    assert live_response.status_code == 200
    assert live_response.json() == {"status": "live"}
    assert ready_response.status_code == 503


def test_readiness_schema_edges_share_safe_internal_reason() -> None:
    for revision in ("deadbeef0001", "not-a-valid-revision!!!", None):
        with pytest.raises(ReadinessError) as exc_info:
            check_readiness(_RevisionDatabase(revision))
        assert exc_info.value.reason == "schema_incompatible"


def test_readiness_bootstrap_incomplete_without_enabled_administrator() -> None:
    with pytest.raises(ReadinessError) as exc_info:
        check_readiness(NoAdministratorDatabase())
    assert exc_info.value.reason == "bootstrap_incomplete"


def test_readiness_object_store_unavailable_when_probe_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(testing=True, source_storage_root=str(tmp_path / "source-storage"))

    def _fail(_root: object) -> None:
        raise ObjectStorageError("Object unavailable.")

    monkeypatch.setattr(readiness_module, "probe_object_store", _fail)
    with pytest.raises(ReadinessError) as exc_info:
        check_readiness(HealthyDatabase(), settings)
    assert exc_info.value.reason == "object_store_unavailable"


def test_readiness_object_store_probe_uses_composed_root(tmp_path: Path) -> None:
    settings = Settings(testing=True, source_storage_root=str(tmp_path / "source-storage"))
    check_readiness(HealthyDatabase(), settings)
    objects_root = tmp_path / "source-storage" / "objects"
    assert objects_root.is_dir()


def test_ready_http_object_store_failure_is_safe_503(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database_path = tmp_path / "health-store.db"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        testing=True,
        source_storage_root=str(tmp_path / "source-storage"),
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)

    with Session(app.state.engine) as db:
        db.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
        db.execute(text("DELETE FROM alembic_version"))
        db.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
            {"version": SUPPORTED_ALEMBIC_HEAD},
        )
        create_user(db, "store-admin@example.test", "Password123!", role=ROLE_ADMINISTRATOR)
        db.commit()

    def _fail(_root: object) -> None:
        raise ObjectStorageError("Object unavailable.")

    monkeypatch.setattr(readiness_module, "probe_object_store", _fail)

    with TestClient(app) as client:
        live_response = client.get("/health/live")
        ready_response = client.get("/health/ready")

    assert live_response.status_code == 200
    assert live_response.json() == {"status": "live"}
    assert ready_response.status_code == 503
    body = ready_response.json()
    assert body["error"]["code"] == "dependency_unavailable"
    assert body["error"]["fields"] == {}
    assert "object" not in ready_response.text.lower()
    assert "storage" not in ready_response.text.lower()
    assert str(tmp_path) not in ready_response.text


def test_ready_stays_ok_with_stopped_domain_and_unready_provider(tmp_path: Path) -> None:
    database_path = tmp_path / "health-domain.db"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        testing=True,
        source_storage_root=str(tmp_path / "source-storage"),
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)

    with Session(app.state.engine) as db:
        db.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
        db.execute(text("DELETE FROM alembic_version"))
        db.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
            {"version": SUPPORTED_ALEMBIC_HEAD},
        )
        seed_runtime_config(db)
        create_user(db, "ready-admin@example.test", "Password123!", role=ROLE_ADMINISTRATOR)
        openai = db.get(ProviderConfig, "openai")
        assert openai is not None
        openai.credential_ciphertext = None
        openai.credential_updated_at = None
        assert not is_provider_configured(openai)
        db.add(
            Domain(
                id="domain-stopped-ready",
                display_name="Stopped Domain",
                state=DOMAIN_STATE_STOPPED,
                embedding_profile_id="openai-embedding-default",
            )
        )
        db.commit()

    with TestClient(app) as client:
        ready_response = client.get("/health/ready")
        live_response = client.get("/health/live")

    assert ready_response.status_code == 200
    assert ready_response.json() == {"status": "ready"}
    assert set(ready_response.json()) == {"status"}
    assert live_response.status_code == 200
    assert live_response.json() == {"status": "live"}
    assert "X-Request-ID" in ready_response.headers or CANONICAL_REQUEST_ID_HEADER in ready_response.headers


def test_schema_edge_ready_http_shares_safe_envelope(tmp_path: Path) -> None:
    database_path = tmp_path / "health-schema.db"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        testing=True,
        source_storage_root=str(tmp_path / "source-storage"),
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    app.dependency_overrides[get_db] = lambda: _RevisionDatabase("ahead-of-head-revision")

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "dependency_unavailable"
    assert body["error"]["fields"] == {}
    assert "ahead" not in response.text.lower()
    assert "alembic" not in response.text.lower()
    assert "schema" not in response.text.lower()
