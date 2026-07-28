"""Deferred Phase 3 Wiki identifiers — recognition seeds for Path 1 refusal.

These names must not appear in the Phase 1 ORM target. Migration preflight and
startup catalog checks use them to classify legacy populated databases.
They are not migration authorization and do not imply a supported upgrade path.
"""

from __future__ import annotations


DEFERRED_WIKI_TABLES: frozenset[str] = frozenset(
    {
        "wiki_pages",
        "wiki_revisions",
        "wiki_contributions",
        "wiki_contribution_evidence_refs",
    }
)

DEFERRED_WIKI_COLUMNS: frozenset[tuple[str, str]] = frozenset(
    {
        ("conversation_turn_composer_refs", "wiki_page_id"),
        ("conversation_turn_composer_refs", "wiki_revision_id"),
    }
)

DEFERRED_COMPOSER_KINDS: frozenset[str] = frozenset({"wiki", "publication"})
