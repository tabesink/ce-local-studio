"""P12-07 U9: HTTP contract for authorized graph snapshot and label search."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from context_engine.api import routes as routes_module
from context_engine.api.contract_app import (
    CANONICAL_API_PREFIX,
    CANONICAL_REQUEST_ID_HEADER,
)
from context_engine.api.dependencies import CurrentSession, require_current_session
from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base
from context_engine.models import User
from context_engine.services.graphs import GraphServiceError


def _http_app(tmp_path: Path, *, role: str = "member"):
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / f'graph-{role}-{uuid4().hex}.db'}",
        testing=True,
        graph_ref_key="unit-test-graph-ref-key-32bytes!!",
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    user = User(
        id=str(uuid4()),
        username=f"{role}@example.test",
        password_hash="synthetic-password-hash",
        role=role,
    )
    app.dependency_overrides[require_current_session] = lambda: CurrentSession(  # type: ignore[arg-type]
        user=user,
        auth_session=None,
    )
    return app


def _snapshot_payload() -> dict[str, object]:
    return {
        "domain": {"ref": "domain-graph-http", "name": "Graph Domain"},
        "nodes": [
            {"ref": "gn_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "label": "Pump", "kind": "equipment", "degree": 1}
        ],
        "edges": [],
        "truncated": False,
    }


@pytest.mark.parametrize("role", ["member", "administrator"])
def test_graph_snapshot_http_returns_closed_private_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
) -> None:
    seen: dict[str, object] = {}

    def snapshot(_db, *, settings, domain_id: str, principal_id: str, label: str | None = None):
        seen.update(
            domain_id=domain_id,
            principal_id=principal_id,
            label=label,
            testing=settings.testing,
        )
        return _snapshot_payload()

    monkeypatch.setattr(routes_module, "get_domain_graph_snapshot", snapshot)
    app = _http_app(tmp_path, role=role)

    with TestClient(app) as client:
        response = client.get(
            f"{CANONICAL_API_PREFIX}/domains/domain-graph-http/graph",
            params={"label": "Pump"},
        )

    assert response.status_code == 200
    assert response.json() == _snapshot_payload()
    assert response.headers["cache-control"] == "private, no-store, no-transform"
    assert response.headers[CANONICAL_REQUEST_ID_HEADER]
    assert seen["domain_id"] == "domain-graph-http"
    assert seen["label"] == "Pump"
    assert seen["testing"] is True
    assert isinstance(seen["principal_id"], str) and seen["principal_id"]


def test_graph_labels_http_returns_closed_projection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def search(_db, *, settings, domain_id: str, principal_id: str, q: str, limit: int = 50):
        assert domain_id == "domain-graph-http"
        assert principal_id
        assert q == "pu"
        assert limit == 10
        return {
            "items": [
                {
                    "nodeRef": "gn_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    "label": "Pump",
                    "kind": "equipment",
                }
            ]
        }

    monkeypatch.setattr(routes_module, "search_domain_graph_labels", search)
    app = _http_app(tmp_path)

    with TestClient(app) as client:
        response = client.get(
            f"{CANONICAL_API_PREFIX}/domains/domain-graph-http/graph/labels",
            params={"q": "pu", "limit": 10},
        )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "items": [
            {
                "nodeRef": "gn_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "label": "Pump",
                "kind": "equipment",
            }
        ]
    }
    assert "q" not in body
    assert response.headers["cache-control"] == "private, no-store, no-transform"


@pytest.mark.parametrize(
    ("status_code", "code", "message", "retry_after"),
    [
        (404, "not_found", "Domain not found.", None),
        (409, "graph_refreshing", "The knowledge graph is refreshing after a corpus change.", None),
        (409, "domain_not_query_eligible", "This knowledge domain is not currently available for queries.", None),
        (429, "rate_limited", "Graph read capacity is temporarily limited.", 1),
        (503, "capacity_unavailable", "Graph read capacity is temporarily unavailable.", None),
        (503, "dependency_unavailable", "Graph runtime is temporarily unavailable.", None),
    ],
)
def test_graph_http_maps_service_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    code: str,
    message: str,
    retry_after: int | None,
) -> None:
    def fail(*_a, **_k):
        raise GraphServiceError(status_code, code, message, retry_after=retry_after)

    monkeypatch.setattr(routes_module, "get_domain_graph_snapshot", fail)
    app = _http_app(tmp_path)

    with TestClient(app) as client:
        response = client.get(f"{CANONICAL_API_PREFIX}/domains/domain-graph-http/graph")

    assert response.status_code == status_code
    body = response.json()
    assert body["error"]["code"] == code
    assert body["error"]["message"] == message
    if retry_after is not None:
        assert response.headers["retry-after"] == str(retry_after)


def test_graph_labels_reject_short_query(tmp_path: Path) -> None:
    app = _http_app(tmp_path)
    with TestClient(app) as client:
        response = client.get(
            f"{CANONICAL_API_PREFIX}/domains/domain-graph-http/graph/labels",
            params={"q": "a"},
        )
    assert response.status_code == 422
