"""http idempotency records

Revision ID: a2c7e9f14b80
Revises: f1a8c3d04e92
Create Date: 2026-07-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a2c7e9f14b80"
down_revision: Union[str, Sequence[str], None] = "f1a8c3d04e92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ROUTE_CLASSES = (
    "conversation.create",
    "model_profile.create",
    "domain.create",
    "domain.start",
    "domain.stop",
    "domain.delete",
    "source.upload",
    "source.retry",
    "source.index_retry",
    "source.delete",
)


def upgrade() -> None:
    op.create_table(
        "http_idempotency_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("principal_user_id", sa.String(length=36), nullable=False),
        sa.Column("route_class", sa.String(length=64), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("response_kind", sa.String(length=64), nullable=True),
        sa.Column("response_refs_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=False), nullable=True),
        sa.ForeignKeyConstraint(["principal_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "principal_user_id",
            "route_class",
            "key_hash",
            name="uq_http_idempotency_principal_route_key",
        ),
        sa.CheckConstraint(
            "route_class in (" + ", ".join(repr(item) for item in _ROUTE_CLASSES) + ")",
            name="ck_http_idempotency_route_class",
        ),
        sa.CheckConstraint(
            "state in ('pending', 'completed')",
            name="ck_http_idempotency_state",
        ),
        sa.CheckConstraint("length(key_hash) = 64", name="ck_http_idempotency_key_hash_size"),
        sa.CheckConstraint(
            "length(fingerprint) = 64",
            name="ck_http_idempotency_fingerprint_size",
        ),
        sa.CheckConstraint(
            "(state = 'pending' AND http_status IS NULL AND response_kind IS NULL "
            "AND response_refs_json IS NULL AND completed_at IS NULL) OR "
            "(state = 'completed' AND http_status IS NOT NULL AND response_kind IS NOT NULL "
            "AND response_refs_json IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_http_idempotency_state_payload",
        ),
    )
    op.create_index(
        "ix_http_idempotency_principal_created",
        "http_idempotency_records",
        ["principal_user_id", sa.text("created_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_http_idempotency_principal_created", table_name="http_idempotency_records")
    op.drop_table("http_idempotency_records")
