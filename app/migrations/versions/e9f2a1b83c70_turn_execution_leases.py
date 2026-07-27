"""turn execution leases

Revision ID: e9f2a1b83c70
Revises: c7d91e5a2f04
Create Date: 2026-07-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e9f2a1b83c70"
down_revision: Union[str, Sequence[str], None] = "c7d91e5a2f04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("conversation_turns") as batch_op:
        batch_op.add_column(sa.Column("lease_owner", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("lease_expires_at", sa.DateTime(timezone=False), nullable=True))
        batch_op.add_column(
            sa.Column(
                "execution_generation",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "events_retained_after",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(sa.Column("claimable_at", sa.DateTime(timezone=False), nullable=True))
        batch_op.create_check_constraint(
            "ck_conversation_turns_execution_generation_nonnegative",
            "execution_generation >= 0",
        )
        batch_op.create_check_constraint(
            "ck_conversation_turns_events_retained_after_nonnegative",
            "events_retained_after >= 0",
        )
        batch_op.create_index(
            "ix_conversation_turns_claimable_lease",
            ["status", "claimable_at", "lease_expires_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("conversation_turns") as batch_op:
        batch_op.drop_index("ix_conversation_turns_claimable_lease")
        batch_op.drop_constraint("ck_conversation_turns_events_retained_after_nonnegative", type_="check")
        batch_op.drop_constraint("ck_conversation_turns_execution_generation_nonnegative", type_="check")
        batch_op.drop_column("claimable_at")
        batch_op.drop_column("events_retained_after")
        batch_op.drop_column("execution_generation")
        batch_op.drop_column("lease_expires_at")
        batch_op.drop_column("lease_owner")
