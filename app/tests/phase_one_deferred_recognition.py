"""Shared Path 1 recognition allowlist for Phase 1 deferred-marker / wiki scans.

These modules may name deferred Wiki tables for refusal recognition; they are not
Wiki implementation. Keep one source of truth for production-scope and schema-scope
gates.
"""

from __future__ import annotations

WIKI_RECOGNITION_ALLOWLIST = frozenset(
    {
        "schema_deferred.py",
        "schema_compatibility.py",
        "generate_schema_snapshot.py",
        "migrate_release.py",
    }
)
