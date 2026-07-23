from __future__ import annotations

from pathlib import Path

from context_engine.db import Base
from context_engine.models import COMPOSER_REF_KINDS
from context_engine.services.audit import ALLOWED_AUDIT_METADATA_KEYS


DEFERRED_WIKI_TABLES = {
    "wiki_pages",
    "wiki_revisions",
    "wiki_contributions",
    "wiki_contribution_evidence_refs",
}
PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "context_engine"


def test_phase_one_metadata_excludes_deferred_wiki_schema() -> None:
    assert DEFERRED_WIKI_TABLES.isdisjoint(Base.metadata.tables)
    assert COMPOSER_REF_KINDS == ("source", "evidence", "template")

    accepted_ref_columns = Base.metadata.tables["conversation_turn_composer_refs"].columns
    assert "wiki_page_id" not in accepted_ref_columns
    assert "wiki_revision_id" not in accepted_ref_columns


def test_phase_one_audit_schema_excludes_deferred_wiki_vocabulary() -> None:
    audit_table = Base.metadata.tables["audit_events"]
    constraint_sql = " ".join(
        str(constraint.sqltext)
        for constraint in audit_table.constraints
        if hasattr(constraint, "sqltext")
    ).casefold()

    assert "wiki." not in constraint_sql
    assert not any("wiki" in key.casefold() for key in ALLOWED_AUDIT_METADATA_KEYS)


def test_active_package_contains_no_deferred_wiki_implementation() -> None:
    assert PACKAGE_ROOT.is_dir()
    assert all(
        "wiki" not in path.read_text().casefold()
        for path in PACKAGE_ROOT.rglob("*.py")
    )
