"""P8-01 denial matrix: contracted admin-route denials and fail-closed audit (KTD8)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import Request

from context_engine.api.dependencies import CurrentSession, require_admin
from context_engine.api.errors import ApiError
from context_engine.models import (
    AUDIT_EVENT_SECURITY_ADMIN_ROUTE_DENIED,
    ROLE_ADMINISTRATOR,
    ROLE_MEMBER,
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
