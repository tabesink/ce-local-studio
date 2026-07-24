"""add login throttle buckets

Revision ID: 8f6c2a91e4b7
Revises: d07141ac7d95
Create Date: 2026-07-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8f6c2a91e4b7"
down_revision: Union[str, Sequence[str], None] = "d07141ac7d95"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "login_throttle_buckets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("client_bucket_hash", sa.String(length=64), nullable=False),
        sa.Column("username_hash", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("blocked_until", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("failure_count >= 0", name="ck_login_throttle_buckets_failure_count"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_login_throttle_buckets_key",
        "login_throttle_buckets",
        ["client_bucket_hash", "username_hash"],
        unique=True,
    )
    op.create_index(
        "ix_login_throttle_buckets_blocked_until",
        "login_throttle_buckets",
        ["blocked_until"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_login_throttle_buckets_blocked_until", table_name="login_throttle_buckets")
    op.drop_index("uq_login_throttle_buckets_key", table_name="login_throttle_buckets")
    op.drop_table("login_throttle_buckets")
