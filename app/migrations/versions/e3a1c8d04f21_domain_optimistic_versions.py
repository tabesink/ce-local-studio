"""domain optimistic versions

Revision ID: e3a1c8d04f21
Revises: b7e2a91c04d8
Create Date: 2026-07-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e3a1c8d04f21"
down_revision: Union[str, Sequence[str], None] = "b7e2a91c04d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "domains",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_check_constraint(
        "ck_domains_version_positive",
        "domains",
        "version >= 1",
    )

    op.add_column(
        "domain_operations",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_check_constraint(
        "ck_domain_operations_version_positive",
        "domain_operations",
        "version >= 1",
    )


def downgrade() -> None:
    op.drop_constraint("ck_domain_operations_version_positive", "domain_operations", type_="check")
    op.drop_column("domain_operations", "version")
    op.drop_constraint("ck_domains_version_positive", "domains", type_="check")
    op.drop_column("domains", "version")
