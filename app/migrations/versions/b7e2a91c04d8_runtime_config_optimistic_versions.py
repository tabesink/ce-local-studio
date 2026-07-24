"""runtime config optimistic versions

Revision ID: b7e2a91c04d8
Revises: c4e8f1a02b93
Create Date: 2026-07-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b7e2a91c04d8"
down_revision: Union[str, Sequence[str], None] = "c4e8f1a02b93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "provider_configs",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_check_constraint(
        "ck_provider_configs_version_positive",
        "provider_configs",
        "version >= 1",
    )

    op.add_column(
        "model_profiles",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_check_constraint(
        "ck_model_profiles_version_positive",
        "model_profiles",
        "version >= 1",
    )

    op.add_column(
        "runtime_settings",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_check_constraint(
        "ck_runtime_settings_version_positive",
        "runtime_settings",
        "version >= 1",
    )


def downgrade() -> None:
    op.drop_constraint("ck_runtime_settings_version_positive", "runtime_settings", type_="check")
    op.drop_column("runtime_settings", "version")
    op.drop_constraint("ck_model_profiles_version_positive", "model_profiles", type_="check")
    op.drop_column("model_profiles", "version")
    op.drop_constraint("ck_provider_configs_version_positive", "provider_configs", type_="check")
    op.drop_column("provider_configs", "version")
