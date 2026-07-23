from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from context_engine.api.contract_app import (
    CANONICAL_API_PREFIX,
    CANONICAL_REQUEST_ID_HEADER,
    register_contract_routes,
)
from context_engine.api.conventions import format_utc_timestamp
from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base


def test_contract_routes_have_one_non_configurable_api_prefix() -> None:
    app = FastAPI()

    register_contract_routes(app)

    paths = set(app.openapi()["paths"])
    assert f"{CANONICAL_API_PREFIX}/auth/login" in paths
    assert not any(path.startswith("/api/") and not path.startswith(f"{CANONICAL_API_PREFIX}/") for path in paths)
    with pytest.raises(TypeError):
        register_contract_routes(FastAPI(), api_prefix="/alternate")  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (datetime(2026, 7, 23, 14, 5, 9, 987654), "2026-07-23T14:05:09Z"),
        (datetime(2026, 7, 23, 14, 5, 9, tzinfo=UTC), "2026-07-23T14:05:09Z"),
        (
            datetime(2026, 7, 23, 10, 5, 9, tzinfo=timezone(timedelta(hours=-4))),
            "2026-07-23T14:05:09Z",
        ),
    ],
)
def test_public_timestamps_are_canonical_rfc3339_utc(value: datetime, expected: str) -> None:
    assert format_utc_timestamp(value) == expected


def test_every_http_response_uses_the_canonical_server_request_id_header(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / "request-id.db"}",
        testing=True,
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)

    with TestClient(app) as client:
        live = client.get("/health/live", headers={CANONICAL_REQUEST_ID_HEADER: "caller-controlled"})
        missing = client.get("/missing")

    assert live.status_code == 200
    assert missing.status_code == 404
    assert 1 <= len(live.headers[CANONICAL_REQUEST_ID_HEADER]) <= 80
    assert live.headers[CANONICAL_REQUEST_ID_HEADER] != "caller-controlled"
    assert missing.json()["error"]["requestId"] == missing.headers[CANONICAL_REQUEST_ID_HEADER]
