"""source block normalized region columns

Revision ID: c9e4b2d17a60
Revises: a2c7e9f14b80
Create Date: 2026-07-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c9e4b2d17a60"
down_revision: Union[str, Sequence[str], None] = "a2c7e9f14b80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_REGION_CHECK = """(
    (
        region_x IS NULL
        AND region_y IS NULL
        AND region_width IS NULL
        AND region_height IS NULL
    )
    OR (
        region_x IS NOT NULL
        AND region_y IS NOT NULL
        AND region_width IS NOT NULL
        AND region_height IS NOT NULL
        AND region_x >= 0 AND region_x <= 1
        AND region_y >= 0 AND region_y <= 1
        AND region_width > 0 AND region_width <= 1
        AND region_height > 0 AND region_height <= 1
        AND region_x + region_width <= 1
        AND region_y + region_height <= 1
    )
)"""


def upgrade() -> None:
    op.add_column("source_blocks", sa.Column("region_x", sa.Float(), nullable=True))
    op.add_column("source_blocks", sa.Column("region_y", sa.Float(), nullable=True))
    op.add_column("source_blocks", sa.Column("region_width", sa.Float(), nullable=True))
    op.add_column("source_blocks", sa.Column("region_height", sa.Float(), nullable=True))
    op.create_check_constraint(
        "ck_source_blocks_region_normalized",
        "source_blocks",
        _REGION_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint("ck_source_blocks_region_normalized", "source_blocks", type_="check")
    op.drop_column("source_blocks", "region_height")
    op.drop_column("source_blocks", "region_width")
    op.drop_column("source_blocks", "region_y")
    op.drop_column("source_blocks", "region_x")
