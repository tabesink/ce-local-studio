"""P8-01 denial matrix: contracted admin-route denials and fail-closed audit (KTD8)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from context_engine.api.contract_app import CANONICAL_API_PREFIX
from context_engine.api.dependencies import CurrentSession, require_admin, require_current_session
from context_engine.api.errors import ApiError
from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base, utc_now
from context_engine.models import (
    AUDIT_EVENT_SECURITY_ADMIN_ROUTE_DENIED,
    ROLE_ADMINISTRATOR,
    ROLE_MEMBER,
    AuthSession,
    User,
)
from context_engine.services.audit import AuditError, AuditService


def _request(*, request_id: str = "req-denial-1") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/admin/users",
        "headers": [(b"x-request-id", request_id.encode("utf-8"))],
    }
    request = Request(scope)
    request.state.request_id = request_id
    return request


def test_require_admin_allows_administrator() -> None:
    admin = SimpleNamespace(id="admin-1", role=ROLE_ADMINISTRATOR)
    current = CurrentSession(user=admin, auth_session=SimpleNamespace())
    assert require_admin(_request(), current, MagicMock()) is admin


def test_require_admin_denies_member_with_audit_then_403(monkeypatch: pytest.MonkeyPatch) -> None:
    member = SimpleNamespace(id="member-1", role=ROLE_MEMBER)
    current = CurrentSession(user=member, auth_session=SimpleNamespace())
    db = MagicMock()
    recorded: dict[str, object] = {}

    def fake_record(self, event_name, **kwargs):  # noqa: ANN001
        recorded["event_name"] = event_name
        recorded.update(kwargs)
        return SimpleNamespace(id="audit-1")

    monkeypatch.setattr(AuditService, "record", fake_record)

    with pytest.raises(ApiError) as exc_info:
        require_admin(_request(), current, db)

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "forbidden"
    assert recorded["event_name"] == AUDIT_EVENT_SECURITY_ADMIN_ROUTE_DENIED
    assert recorded.get("target_id") is None
    assert recorded.get("target_kind") is None
    db.commit.assert_called_once()


def test_require_admin_audit_record_failure_is_503_audit_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    member = SimpleNamespace(id="member-1", role=ROLE_MEMBER)
    current = CurrentSession(user=member, auth_session=SimpleNamespace())
    db = MagicMock()

    def fail_record(self, *args, **kwargs):  # noqa: ANN001
        raise AuditError()

    monkeypatch.setattr(AuditService, "record", fail_record)

    with pytest.raises(AuditError) as exc_info:
        require_admin(_request(), current, db)

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "audit_unavailable"
    db.commit.assert_not_called()


def test_require_admin_audit_commit_failure_maps_to_audit_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    member = SimpleNamespace(id="member-1", role=ROLE_MEMBER)
    current = CurrentSession(user=member, auth_session=SimpleNamespace())
    db = MagicMock()
    db.commit.side_effect = RuntimeError("commit failed")

    monkeypatch.setattr(AuditService, "record", lambda self, *a, **k: SimpleNamespace(id="a1"))

    with pytest.raises(AuditError) as exc_info:
        require_admin(_request(), current, db)

    assert exc_info.value.code == "audit_unavailable"
    db.rollback.assert_called()


def test_member_admin_http_audit_failure_returns_503_audit_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database_path = tmp_path / f"denial-http-{uuid4().hex}.db"
    # testing=True with no ingress knobs disables request-security so the
    # TestClient exercise focuses on require_admin → AuditError → HTTP envelope.
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        testing=True,
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    db = app.state.session_factory()
    try:
        member = User(
            username="denial-http-member@example.test",
            password_hash="synthetic-password-hash",
            role=ROLE_MEMBER,
        )
        now = utc_now()
        auth_session = AuthSession(
            user=member,
            token_hash="b" * 64,
            expires_at=now + timedelta(hours=1),
            created_at=now,
            last_used_at=now,
        )
        db.add_all([member, auth_session])
        db.commit()
        db.refresh(member)
        db.refresh(auth_session)
        member_id = member.id
        auth_session_id = auth_session.id
    finally:
        db.close()

    identity_db = app.state.session_factory()
    identity = identity_db.get(User, member_id)
    identity_session = identity_db.get(AuthSession, auth_session_id)
    assert identity is not None and identity_session is not None
    app.dependency_overrides[require_current_session] = lambda: CurrentSession(
        user=identity,
        auth_session=identity_session,
    )

    def fail_record(self, *args, **kwargs):  # noqa: ANN001
        raise AuditError()

    monkeypatch.setattr(AuditService, "record", fail_record)

    try:
        with TestClient(app) as client:
            response = client.get(
                f"{CANONICAL_API_PREFIX}/admin/users",
                headers={"X-Request-Id": "req-denial-http-1"},
            )
        body = response.json()
        assert response.status_code == 503
        assert response.headers["cache-control"] == "private, no-store, no-transform"
        assert body["error"]["code"] == "audit_unavailable"
        assert body["error"]["message"] == "Audit unavailable."
        assert body["error"]["requestId"]
        assert "fields" in body["error"]
        assert "Traceback" not in response.text
        assert "AuditError" not in response.text
        assert set(body["error"]) == {"code", "message", "requestId", "fields"}
    finally:
        app.dependency_overrides.clear()
        identity_db.close()
        app.state.engine.dispose()
