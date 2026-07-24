"""audit events append-only triggers

Revision ID: c4e8f1a02b93
Revises: 8f6c2a91e4b7
Create Date: 2026-07-24
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c4e8f1a02b93"
down_revision: Union[str, Sequence[str], None] = "8f6c2a91e4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION ce_forbid_audit_events_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          RAISE EXCEPTION 'audit_events is append-only'
            USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_events_forbid_update
          BEFORE UPDATE ON audit_events
          FOR EACH ROW
          EXECUTE FUNCTION ce_forbid_audit_events_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_events_forbid_delete
          BEFORE DELETE ON audit_events
          FOR EACH ROW
          EXECUTE FUNCTION ce_forbid_audit_events_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_forbid_update ON audit_events")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_forbid_delete ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS ce_forbid_audit_events_mutation()")
