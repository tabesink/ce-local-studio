"""source delete operations and audit events

Revision ID: b5c8e2d19f47
Revises: a8d3f1c62e90
Create Date: 2026-07-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b5c8e2d19f47"
down_revision: Union[str, Sequence[str], None] = "a8d3f1c62e90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_AUDIT_EVENT_NAMES = (
    "runtime_settings.provider_config_rotated",
    "runtime_settings.model_profile_created",
    "runtime_settings.model_profile_updated",
    "runtime_settings.model_profile_deleted",
    "runtime_settings.defaults_updated",
    "domain.created",
    "domain.started",
    "domain.stopped",
    "domain.delete_queued",
    "domain.delete_succeeded",
    "domain.delete_failed",
    "source.uploaded",
    "source.preparation_retried",
    "source.preparation_cancelled",
    "source.deleted",
    "source.delete_queued",
    "source.delete_succeeded",
    "source.delete_failed",
    "source.index_retry_queued",
    "source.index_cancelled",
    "chat.turn_redacted",
    "security.admin_route_denied",
    "user.disabled",
    "user.enabled",
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_source_preparation_operations_type",
        "source_preparation_operations",
        type_="check",
    )
    op.create_check_constraint(
        "ck_source_preparation_operations_type",
        "source_preparation_operations",
        "operation_type in ('prepare', 'delete')",
    )

    op.drop_constraint("ck_audit_events_event_name", "audit_events", type_="check")
    quoted = ", ".join(f"'{name}'" for name in _AUDIT_EVENT_NAMES)
    op.create_check_constraint(
        "ck_audit_events_event_name",
        "audit_events",
        f"event_name in ({quoted})",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_source_preparation_operations_type",
        "source_preparation_operations",
        type_="check",
    )
    op.create_check_constraint(
        "ck_source_preparation_operations_type",
        "source_preparation_operations",
        "operation_type in ('prepare')",
    )

    prior = (
        "runtime_settings.provider_config_rotated",
        "runtime_settings.model_profile_created",
        "runtime_settings.model_profile_updated",
        "runtime_settings.model_profile_deleted",
        "runtime_settings.defaults_updated",
        "domain.created",
        "domain.started",
        "domain.stopped",
        "domain.delete_queued",
        "domain.delete_succeeded",
        "domain.delete_failed",
        "source.uploaded",
        "source.preparation_retried",
        "source.preparation_cancelled",
        "source.deleted",
        "source.index_retry_queued",
        "source.index_cancelled",
        "chat.turn_redacted",
        "security.admin_route_denied",
        "user.disabled",
        "user.enabled",
    )
    op.drop_constraint("ck_audit_events_event_name", "audit_events", type_="check")
    quoted = ", ".join(f"'{name}'" for name in prior)
    op.create_check_constraint(
        "ck_audit_events_event_name",
        "audit_events",
        f"event_name in ({quoted})",
    )
