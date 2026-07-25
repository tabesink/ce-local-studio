from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from context_engine.models import (
    DOMAIN_OPERATION_START,
    DOMAIN_OPERATION_STATUS_FAILED,
    DOMAIN_OPERATION_STATUS_RUNNING,
    DOMAIN_OPERATION_STATUS_SUCCEEDED,
    DOMAIN_STATE_DELETING,
    DOMAIN_STATE_RUNNING,
    DOMAIN_STATE_STOPPED,
    Domain,
    DomainOperation,
    ModelProfile,
    PROFILE_EMBEDDING,
    PROVIDER_OPENAI,
)
from context_engine.services.domains import (
    DomainError,
    _domain_allowed_actions,
    safe_domain_admin,
    safe_domain_operation,
    safe_member_domain,
)


class _HealthyController:
    def health(self, _domain: Domain):
        class _Health:
            healthy = True

        return _Health()


def _domain(*, state: str = DOMAIN_STATE_STOPPED, version: int = 1, generation: int = 1) -> Domain:
    profile = ModelProfile(
        id="openai-embedding-default",
        name="OpenAI Default Embedding",
        profile_kind=PROFILE_EMBEDDING,
        provider_kind=PROVIDER_OPENAI,
        model_name="text-embedding-3-small",
        vector_dimensions=1536,
    )
    domain = Domain(
        id="domain-manuals",
        display_name="Equipment Manuals",
        state=state,
        embedding_profile_id=profile.id,
        runtime_instance_id=str(uuid4()),
        control_generation=generation,
        version=version,
        created_at=datetime(2026, 7, 25, 12, 0, 0),
        updated_at=datetime(2026, 7, 25, 12, 0, 0),
    )
    domain.embedding_profile = profile
    return domain


def _operation(domain: Domain, *, status: str = DOMAIN_OPERATION_STATUS_SUCCEEDED) -> DomainOperation:
    return DomainOperation(
        id=str(uuid4()),
        domain_id=domain.id,
        operation_type=DOMAIN_OPERATION_START,
        status=status,
        control_generation_at_start=domain.control_generation,
        message="Domain started.",
        error_code="dependency_unavailable" if status == DOMAIN_OPERATION_STATUS_FAILED else None,
        error_message="Runtime unavailable." if status == DOMAIN_OPERATION_STATUS_FAILED else None,
        version=2,
        started_at=datetime(2026, 7, 25, 12, 1, 0),
        finished_at=datetime(2026, 7, 25, 12, 2, 0) if status != DOMAIN_OPERATION_STATUS_RUNNING else None,
        created_at=datetime(2026, 7, 25, 12, 1, 0),
        updated_at=datetime(2026, 7, 25, 12, 2, 0),
    )


class _Session:
    def __init__(self, active: DomainOperation | None = None) -> None:
        self._active = active

    def scalar(self, _statement):
        return self._active

    def get(self, model, key):
        return None


def test_safe_domain_operation_projects_closed_operation_dto() -> None:
    domain = _domain(generation=3)
    operation = _operation(domain, status=DOMAIN_OPERATION_STATUS_FAILED)
    projected = safe_domain_operation(operation)
    assert set(projected) == {
        "id",
        "targetKind",
        "targetRef",
        "operationType",
        "status",
        "generation",
        "message",
        "error",
        "requestedAt",
        "startedAt",
        "finishedAt",
        "version",
        "allowedActions",
    }
    assert projected["targetKind"] == "domain"
    assert projected["targetRef"] == domain.id
    assert projected["generation"] == 3
    assert projected["error"] == {"code": "dependency_unavailable", "message": "Runtime unavailable."}
    assert "errorCode" not in projected
    assert "createdAt" not in projected
    assert projected["requestedAt"].endswith("Z")


def test_safe_member_and_admin_projections_drop_uncontracted_fields() -> None:
    domain = _domain(state=DOMAIN_STATE_RUNNING, version=4, generation=2)
    member = safe_member_domain(domain)
    assert member == {
        "id": "domain-manuals",
        "displayName": "Equipment Manuals",
        "state": DOMAIN_STATE_RUNNING,
        "queryEligible": True,
    }
    assert "available" not in member

    admin = safe_domain_admin(_Session(), settings=None, domain=domain, controller=_HealthyController())  # type: ignore[arg-type]
    assert admin["queryEligible"] is True
    assert admin["runtimeReady"] is True
    assert admin["controlGeneration"] == 2
    assert admin["version"] == 4
    assert admin["embeddingProfile"] == {
        "id": "openai-embedding-default",
        "name": "OpenAI Default Embedding",
        "vectorDimensions": 1536,
    }
    assert "storageSummary" not in admin
    assert "embeddingProfileId" not in admin
    assert "available" not in admin
    assert {row["action"] for row in admin["allowedActions"]} == {"start", "stop", "delete"}


def test_domain_allowed_actions_respect_state_and_active_operation() -> None:
    stopped = _domain(state=DOMAIN_STATE_STOPPED)
    actions = {row["action"]: row for row in _domain_allowed_actions(stopped, None)}
    assert actions["start"]["enabled"] is True
    assert actions["stop"]["enabled"] is False
    assert actions["stop"]["reasonCode"] == "domain_state_conflict"

    running = _domain(state=DOMAIN_STATE_RUNNING)
    busy = _operation(running, status=DOMAIN_OPERATION_STATUS_RUNNING)
    busy_actions = {row["action"]: row for row in _domain_allowed_actions(running, busy)}
    assert all(row["enabled"] is False for row in busy_actions.values())
    assert busy_actions["delete"]["reasonCode"] == "domain_operation_in_progress"

    deleting = _domain(state=DOMAIN_STATE_DELETING)
    delete_actions = {row["action"]: row for row in _domain_allowed_actions(deleting, None)}
    assert all(row["enabled"] is False for row in delete_actions.values())


def test_require_domain_version_maps_to_stale_revision() -> None:
    from context_engine.services.domains import _require_domain_version

    domain = _domain(version=2)
    with pytest.raises(DomainError) as exc_info:
        _require_domain_version(domain, 1)
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "stale_revision"
