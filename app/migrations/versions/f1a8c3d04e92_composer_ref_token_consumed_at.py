"""composer ref token consumed_at

Revision ID: f1a8c3d04e92
Revises: e9f2a1b83c70
Create Date: 2026-07-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f1a8c3d04e92"
down_revision: Union[str, Sequence[str], None] = "e9f2a1b83c70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("composer_ref_tokens") as batch_op:
        batch_op.add_column(sa.Column("consumed_at", sa.DateTime(timezone=False), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("composer_ref_tokens") as batch_op:
        batch_op.drop_column("consumed_at")
