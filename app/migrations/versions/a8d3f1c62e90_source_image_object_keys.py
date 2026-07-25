"""source image object keys

Revision ID: a8d3f1c62e90
Revises: f4b2c9e18a70
Create Date: 2026-07-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a8d3f1c62e90"
down_revision: Union[str, Sequence[str], None] = "f4b2c9e18a70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "source_images",
        sa.Column("object_key", sa.String(length=128), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE source_images "
            "SET object_key = 'legacy_img_' || replace(id, '-', '') "
            "WHERE object_key IS NULL"
        )
    )
    op.alter_column("source_images", "object_key", nullable=False)
    op.create_index(
        "uq_source_images_object_key",
        "source_images",
        ["object_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_source_images_object_key", table_name="source_images")
    op.drop_column("source_images", "object_key")
