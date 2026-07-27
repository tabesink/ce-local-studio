"""conversation ownership foundation

Revision ID: c7d91e5a2f04
Revises: b5c8e2d19f47
Create Date: 2026-07-26
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c7d91e5a2f04"
down_revision: Union[str, Sequence[str], None] = "b5c8e2d19f47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PRIOR_AUDIT_EVENT_NAMES = (
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
_CONVERSATION_AUDIT_EVENT_NAMES = (
    "conversation.created",
    "conversation.renamed",
    "conversation.deleted",
)


def _replace_audit_event_constraint(names: tuple[str, ...]) -> None:
    quoted = ", ".join(f"'{name}'" for name in names)
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.drop_constraint("ck_audit_events_event_name", type_="check")
        batch_op.create_check_constraint(
            "ck_audit_events_event_name",
            f"event_name in ({quoted})",
        )


def _backfill_public_ref(table_name: str, prefix: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                f"UPDATE {table_name} "
                f"SET public_ref = '{prefix}_' || replace(gen_random_uuid()::text, '-', '') "
                "WHERE public_ref IS NULL"
            )
        )
        return
    ids = bind.execute(sa.text(f"SELECT id FROM {table_name} WHERE public_ref IS NULL")).scalars()
    for internal_id in ids:
        bind.execute(
            sa.text(f"UPDATE {table_name} SET public_ref = :public_ref WHERE id = :internal_id"),
            {"public_ref": f"{prefix}_{uuid.uuid4().hex}", "internal_id": internal_id},
        )


def _postgres_public_ref_default(prefix: str) -> sa.TextClause:
    return sa.text(f"'{prefix}_' || replace(gen_random_uuid()::text, '-', '')")


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column("conversations", sa.Column("public_ref", sa.String(length=64), nullable=True))
    op.add_column(
        "conversations",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column("conversation_turns", sa.Column("public_ref", sa.String(length=64), nullable=True))

    _backfill_public_ref("conversations", "conv")
    _backfill_public_ref("conversation_turns", "turn")

    conversation_default = _postgres_public_ref_default("conv") if bind.dialect.name == "postgresql" else None
    turn_default = _postgres_public_ref_default("turn") if bind.dialect.name == "postgresql" else None
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.alter_column(
            "public_ref",
            existing_type=sa.String(length=64),
            nullable=False,
            server_default=conversation_default,
        )
        batch_op.create_check_constraint("ck_conversations_version_positive", "version >= 1")
        batch_op.create_index("uq_conversations_public_ref", ["public_ref"], unique=True)
        batch_op.create_index(
            "ix_conversations_owner_created",
            ["owner_user_id", sa.text("created_at DESC"), sa.text("id DESC")],
            unique=False,
        )
    with op.batch_alter_table("conversation_turns") as batch_op:
        batch_op.alter_column(
            "public_ref",
            existing_type=sa.String(length=64),
            nullable=False,
            server_default=turn_default,
        )
        batch_op.create_index("uq_conversation_turns_public_ref", ["public_ref"], unique=True)

    _replace_audit_event_constraint(_PRIOR_AUDIT_EVENT_NAMES + _CONVERSATION_AUDIT_EVENT_NAMES)


def downgrade() -> None:
    # Conversation audit rows are append-only. Keep the additive event-name
    # allowlist so a rollback remains possible after the feature has been used.
    with op.batch_alter_table("conversation_turns") as batch_op:
        batch_op.drop_index("uq_conversation_turns_public_ref")
        batch_op.drop_column("public_ref")
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_index("ix_conversations_owner_created")
        batch_op.drop_index("uq_conversations_public_ref")
        batch_op.drop_constraint("ck_conversations_version_positive", type_="check")
        batch_op.drop_column("version")
        batch_op.drop_column("public_ref")
