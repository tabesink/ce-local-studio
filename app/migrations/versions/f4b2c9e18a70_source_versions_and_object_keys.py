"""source versions and object keys

Revision ID: f4b2c9e18a70
Revises: e3a1c8d04f21
Create Date: 2026-07-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f4b2c9e18a70"
down_revision: Union[str, Sequence[str], None] = "e3a1c8d04f21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "source_documents",
        sa.Column("original_object_key", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "source_documents",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_check_constraint(
        "ck_source_documents_version_positive",
        "source_documents",
        "version >= 1",
    )

    op.execute(
        sa.text(
            "UPDATE source_documents "
            "SET original_object_key = 'legacy_' || replace(id, '-', '') "
            "WHERE original_object_key IS NULL"
        )
    )
    op.alter_column("source_documents", "original_object_key", nullable=False)
    op.create_index(
        "uq_source_documents_original_object_key",
        "source_documents",
        ["original_object_key"],
        unique=True,
    )

    op.add_column(
        "source_preparation_operations",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_check_constraint(
        "ck_source_preparation_operations_version_positive",
        "source_preparation_operations",
        "version >= 1",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_source_preparation_operations_version_positive",
        "source_preparation_operations",
        type_="check",
    )
    op.drop_column("source_preparation_operations", "version")
    op.drop_index("uq_source_documents_original_object_key", table_name="source_documents")
    op.drop_constraint("ck_source_documents_version_positive", "source_documents", type_="check")
    op.drop_column("source_documents", "version")
    op.drop_column("source_documents", "original_object_key")
