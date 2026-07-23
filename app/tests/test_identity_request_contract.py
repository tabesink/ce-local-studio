from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from context_engine.api import routes as routes_module
from context_engine.api.contract_app import (
    CANONICAL_API_PREFIX,
    CANONICAL_REQUEST_ID_HEADER,
    register_contract_routes,
)
from context_engine.api.routes import LoginRequest
from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("", "valid-password"),
        ("u" * 321, "valid-password"),
        ("valid-user", ""),
        ("valid-user", "p" * 1025),
    ],
)
def test_login_request_rejects_catalog_boundary_violations(username: str, password: str) -> None:
    with pytest.raises(ValidationError):
        LoginRequest.model_validate({"username": username, "password": password})


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("u", "p"),
        ("u" * 320, "p"),
        ("u", "p" * 1024),
    ],
)
def test_login_request_accepts_catalog_boundaries(username: str, password: str) -> None:
    request = LoginRequest.model_validate({"username": username, "password": password})

    assert request.username == username
    assert request.password == password


def test_login_request_rejects_unknown_and_missing_fields() -> None:
    with pytest.raises(ValidationError):
        LoginRequest.model_validate({"username": "user", "password": "password", "session": "forbidden"})
    with pytest.raises(ValidationError):
        LoginRequest.model_validate({"password": "password"})
    with pytest.raises(ValidationError):
        LoginRequest.model_validate({"username": "user"})


def test_login_request_openapi_schema_is_closed_and_bounded() -> None:
    app = FastAPI()
    register_contract_routes(app)
    document = app.openapi()
    login_operation = document["paths"][f"{CANONICAL_API_PREFIX}/auth/login"]["post"]
    request_schema = login_operation["requestBody"]["content"]["application/json"]["schema"]
    schema = document["components"]["schemas"]["LoginRequest"]

    assert request_schema == {"$ref": "#/components/schemas/LoginRequest"}
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"username", "password"}
    assert schema["properties"]["username"]["minLength"] == 1
    assert schema["properties"]["username"]["maxLength"] == 320
    assert schema["properties"]["password"]["minLength"] == 1
    assert schema["properties"]["password"]["maxLength"] == 1024


@pytest.mark.parametrize(
    ("payload", "invalid_field"),
    [
        ({"username": "u" * 321, "password": "p"}, "username"),
        ({"username": "user", "password": "sensitive-marker" + "p" * 1024}, "password"),
        ({"username": "user", "password": "p", "session": "sensitive-marker"}, "session"),
        ({"password": "p"}, "username"),
        ({"username": "user"}, "password"),
    ],
)
def test_login_http_validation_fails_safely_before_authentication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, str],
    invalid_field: str,
) -> None:
    authentication_called = False

    def unexpected_authentication(*_args: object) -> None:
        nonlocal authentication_called
        authentication_called = True

    monkeypatch.setattr(routes_module, "authenticate_user", unexpected_authentication)
    database_path = tmp_path / "identity.db"
    settings = Settings(database_url=f"sqlite+pysqlite:///{database_path}", testing=True)
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)

    with TestClient(app) as client:
        response = client.post(f"{CANONICAL_API_PREFIX}/auth/login", json=payload)

    body = response.json()
    assert response.status_code == 422
    assert body["error"] == {
        "code": "validation_error",
        "message": "Request validation failed.",
        "requestId": response.headers[CANONICAL_REQUEST_ID_HEADER],
        "fields": {invalid_field: "Invalid value."},
    }
    assert "sensitive-marker" not in response.text
    assert authentication_called is False
