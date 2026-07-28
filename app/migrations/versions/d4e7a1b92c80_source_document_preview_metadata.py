"""source document governed preview metadata

Revision ID: d4e7a1b92c80
Revises: c9e4b2d17a60
Create Date: 2026-07-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d4e7a1b92c80"
down_revision: Union[str, Sequence[str], None] = "c9e4b2d17a60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PREVIEW_STATE_CHECK = (
    "preview_state in ("
    "'not_requested', 'queued', 'running', 'ready', 'failed'"
    ")"
)


def upgrade() -> None:
    op.add_column(
        "source_documents",
        sa.Column("preview_state", sa.String(length=16), nullable=False, server_default="not_requested"),
    )
    op.add_column(
        "source_documents",
        sa.Column("preview_generation", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "source_documents",
        sa.Column("preview_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("source_documents", sa.Column("preview_object_key", sa.String(length=128), nullable=True))
    op.add_column("source_documents", sa.Column("preview_sha256", sa.String(length=64), nullable=True))
    op.add_column("source_documents", sa.Column("preview_size_bytes", sa.Integer(), nullable=True))
    op.add_column("source_documents", sa.Column("preview_page_count", sa.Integer(), nullable=True))
    op.add_column(
        "source_documents",
        sa.Column("preview_renderer_version", sa.String(length=64), nullable=True),
    )
    op.add_column("source_documents", sa.Column("preview_source_sha256", sa.String(length=64), nullable=True))
    op.add_column(
        "source_documents",
        sa.Column("preview_page_map_object_key", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "source_documents",
        sa.Column("preview_page_map_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "source_documents",
        sa.Column("preview_reuses_original", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("source_documents", sa.Column("preview_error_code", sa.String(length=64), nullable=True))
    op.add_column(
        "source_documents",
        sa.Column("preview_error_message", sa.String(length=500), nullable=True),
    )
    op.add_column("source_documents", sa.Column("preview_lease_owner", sa.String(length=64), nullable=True))
    op.add_column(
        "source_documents",
        sa.Column("preview_lease_expires_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "source_documents",
        sa.Column("preview_ready_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "source_documents",
        sa.Column("preview_updated_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.create_check_constraint(
        "ck_source_documents_preview_state",
        "source_documents",
        _PREVIEW_STATE_CHECK,
    )
    op.create_check_constraint(
        "ck_source_documents_preview_generation_nonnegative",
        "source_documents",
        "preview_generation >= 0",
    )
    op.create_check_constraint(
        "ck_source_documents_preview_version_nonnegative",
        "source_documents",
        "preview_version >= 0",
    )
    op.create_index(
        "uq_source_documents_preview_object_key",
        "source_documents",
        ["preview_object_key"],
        unique=True,
    )
    op.create_index(
        "uq_source_documents_preview_page_map_object_key",
        "source_documents",
        ["preview_page_map_object_key"],
        unique=True,
    )
    op.create_index(
        "ix_source_documents_domain_preview_state",
        "source_documents",
        ["domain_id", "preview_state"],
        unique=False,
    )
    # Drop server defaults after backfill so ORM/application defaults own inserts.
    op.alter_column("source_documents", "preview_state", server_default=None)
    op.alter_column("source_documents", "preview_generation", server_default=None)
    op.alter_column("source_documents", "preview_version", server_default=None)
    op.alter_column("source_documents", "preview_reuses_original", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_source_documents_domain_preview_state", table_name="source_documents")
    op.drop_index("uq_source_documents_preview_page_map_object_key", table_name="source_documents")
    op.drop_index("uq_source_documents_preview_object_key", table_name="source_documents")
    op.drop_constraint("ck_source_documents_preview_version_nonnegative", "source_documents", type_="check")
    op.drop_constraint("ck_source_documents_preview_generation_nonnegative", "source_documents", type_="check")
    op.drop_constraint("ck_source_documents_preview_state", "source_documents", type_="check")
    for column in (
        "preview_updated_at",
        "preview_ready_at",
        "preview_lease_expires_at",
        "preview_lease_owner",
        "preview_error_message",
        "preview_error_code",
        "preview_reuses_original",
        "preview_page_map_sha256",
        "preview_page_map_object_key",
        "preview_source_sha256",
        "preview_renderer_version",
        "preview_page_count",
        "preview_size_bytes",
        "preview_sha256",
        "preview_object_key",
        "preview_version",
        "preview_generation",
        "preview_state",
    ):
        op.drop_column("source_documents", column)
