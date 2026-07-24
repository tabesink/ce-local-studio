"""add public refs and cancelled turns

Revision ID: d07141ac7d95
Revises: 014b33300438
Create Date: 2026-07-24 09:17:08.081283

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd07141ac7d95'
down_revision: Union[str, Sequence[str], None] = '014b33300438'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PUBLIC_REF_TARGETS = (
    ("source_documents", "uq_source_documents_public_ref", "doc"),
    ("conversation_turn_evidence_refs", "uq_conversation_turn_evidence_refs_public_ref", "ev"),
    ("conversation_turn_composer_refs", "uq_conversation_turn_composer_refs_public_ref", "accepted"),
)


def _restore_sqlite_expression_index(table_name: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite" and table_name == "source_documents":
        existing_indexes = {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}
        if "ix_source_documents_domain_created" in existing_indexes:
            return
        op.create_index(
            "ix_source_documents_domain_created",
            table_name,
            ["domain_id", sa.text("created_at DESC")],
            unique=False,
        )


def _add_public_ref(table_name: str, index_name: str, prefix: str) -> None:
    op.add_column(table_name, sa.Column("public_ref", sa.String(length=64), nullable=True))
    bind = op.get_bind()
    internal_ids = bind.execute(
        sa.text(f"SELECT id FROM {table_name} WHERE public_ref IS NULL")
    ).scalars()
    for internal_id in internal_ids:
        bind.execute(
            sa.text(f"UPDATE {table_name} SET public_ref = :public_ref WHERE id = :internal_id"),
            {"public_ref": f"{prefix}_{uuid.uuid4().hex}", "internal_id": internal_id},
        )
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.alter_column("public_ref", existing_type=sa.String(length=64), nullable=False)
        batch_op.create_index(index_name, ["public_ref"], unique=True)
    _restore_sqlite_expression_index(table_name)


def _drop_public_ref(table_name: str, index_name: str) -> None:
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.drop_index(index_name)
        batch_op.drop_column("public_ref")
    _restore_sqlite_expression_index(table_name)


def _replace_turn_status_constraint(statuses: tuple[str, ...]) -> None:
    with op.batch_alter_table("conversation_turns") as batch_op:
        batch_op.drop_constraint("ck_conversation_turns_status", type_="check")
        batch_op.create_check_constraint("ck_conversation_turns_status", f"status in {statuses}")
    bind = op.get_bind()
    existing_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("conversation_turns")}
    if bind.dialect.name == "sqlite" and "ix_conversation_turns_conversation_created" not in existing_indexes:
        op.create_index(
            "ix_conversation_turns_conversation_created",
            "conversation_turns",
            ["conversation_id", sa.text("created_at DESC")],
            unique=False,
        )


def upgrade() -> None:
    """Upgrade schema."""
    for table_name, index_name, prefix in PUBLIC_REF_TARGETS:
        _add_public_ref(table_name, index_name, prefix)
    _replace_turn_status_constraint(("running", "completed", "failed", "cancelled", "redacted"))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE conversation_turns SET status = 'failed' WHERE status = 'cancelled'")
    _replace_turn_status_constraint(("running", "completed", "failed", "redacted"))
    for table_name, index_name, _prefix in reversed(PUBLIC_REF_TARGETS):
        _drop_public_ref(table_name, index_name)
