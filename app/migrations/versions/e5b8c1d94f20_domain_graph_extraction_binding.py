"""domain graph extraction binding, indexing latch, graph generations

Revision ID: e5b8c1d94f20
Revises: d4e7a1b92c80
Create Date: 2026-07-28

Expand/migrate/contract:
  1. Expand: add nullable graph_extraction_profile_id, latch, and generation columns.
  2. Migrate: backfill indexing_ever_started=true where any source index history or
     remote index artifact exists (or history is ambiguous). Leave
     graph_extraction_profile_id NULL for legacy domains (one-time assignment only
     when latch remains false). Generations start at 0.
  3. Contract: enforce NOT NULL on latch/generation columns (already via server
     defaults + ALTER). Extraction FK stays nullable for ineligible legacy rows;
     application requires it for new creates.

Rollback notes:
  Downgrade drops the four columns and the new FK/index. Domains created after
  this revision lose extraction bindings and latch/generation state. Restore from
  backup before downgrade if those bindings must be preserved. Do not downgrade
  a deployment that has already started indexing under the new latch semantics
  without an explicit restore plan.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e5b8c1d94f20"
down_revision: Union[str, Sequence[str], None] = "d4e7a1b92c80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "domains",
        sa.Column("graph_extraction_profile_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "domains",
        sa.Column(
            "indexing_ever_started",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "domains",
        sa.Column(
            "graph_desired_generation",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "domains",
        sa.Column(
            "graph_applied_generation",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_foreign_key(
        "fk_domains_graph_extraction_profile_id_model_profiles",
        "domains",
        "model_profiles",
        ["graph_extraction_profile_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_domains_graph_extraction_profile_id",
        "domains",
        ["graph_extraction_profile_id"],
    )
    op.create_check_constraint(
        "ck_domains_graph_desired_generation_nonneg",
        "domains",
        "graph_desired_generation >= 0",
    )
    op.create_check_constraint(
        "ck_domains_graph_applied_generation_nonneg",
        "domains",
        "graph_applied_generation >= 0",
    )

    # Latch true when any durable index history exists (or is ambiguous).
    op.execute(
        """
        UPDATE domains AS d
        SET indexing_ever_started = true
        WHERE EXISTS (
            SELECT 1
            FROM source_documents AS s
            WHERE s.domain_id = d.id
              AND (
                    s.index_state IS DISTINCT FROM 'not_requested'
                 OR s.index_generation > 0
                 OR s.index_request_id IS NOT NULL
                 OR s.index_remote_document_id IS NOT NULL
                 OR s.index_content_hash IS NOT NULL
              )
        )
        """
    )

    op.alter_column("domains", "indexing_ever_started", server_default=None)
    op.alter_column("domains", "graph_desired_generation", server_default=None)
    op.alter_column("domains", "graph_applied_generation", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_domains_graph_applied_generation_nonneg", "domains", type_="check")
    op.drop_constraint("ck_domains_graph_desired_generation_nonneg", "domains", type_="check")
    op.drop_index("ix_domains_graph_extraction_profile_id", table_name="domains")
    op.drop_constraint(
        "fk_domains_graph_extraction_profile_id_model_profiles",
        "domains",
        type_="foreignkey",
    )
    op.drop_column("domains", "graph_applied_generation")
    op.drop_column("domains", "graph_desired_generation")
    op.drop_column("domains", "indexing_ever_started")
    op.drop_column("domains", "graph_extraction_profile_id")
