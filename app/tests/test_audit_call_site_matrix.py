"""P8-01 call-site matrix: migrate sites must use commit_protected_mutation."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import context_engine.services.indexing as indexing_mod
import context_engine.services.sources as sources_mod

_MIGRATE_FUNCTIONS = {
    sources_mod: ("retry_source", "cancel_source"),
    indexing_mod: ("retry_source_index", "cancel_source_index"),
}

_EXEMPT_RECORD_MODULES = {
    # Inventory exemptions: open-txn upload, worker terminals, nested redaction, denial.
    "context_engine.services.sources": {
        "upload_source_bytes",
        # SourceDeleteWorker methods — names vary; allow module-level record for workers
    },
}


def _function_source(module: object, name: str) -> str:
    fn = getattr(module, name)
    return inspect.getsource(fn)


def test_migrate_sites_call_commit_protected_mutation() -> None:
    for module, names in _MIGRATE_FUNCTIONS.items():
        for name in names:
            src = _function_source(module, name)
            assert "commit_protected_mutation" in src, f"{module.__name__}.{name} must use commit_protected_mutation"
            assert "AuditService(" not in src, (
                f"{module.__name__}.{name} must not use ad-hoc AuditService.record; inventory tags it migrate"
            )


def test_inventory_lists_every_closed_audit_event() -> None:
    from context_engine.models import AUDIT_EVENT_NAMES

    inventory = Path(__file__).resolve().parents[2] / "docs" / "_scratch" / "p8-01-audit-inventory.md"
    text = inventory.read_text(encoding="utf-8")
    missing = [name for name in AUDIT_EVENT_NAMES if f"`{name}`" not in text]
    assert missing == [], f"inventory missing closed events: {missing}"


def test_sources_module_still_allows_exempt_adhoc_record() -> None:
    """Upload and worker terminals remain ad-hoc per inventory exemptions."""
    tree = ast.parse(Path(sources_mod.__file__).read_text(encoding="utf-8"))
    record_calls = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "record":
                record_calls += 1
    assert record_calls >= 1, "expected exempt ad-hoc AuditService.record sites to remain in sources.py"
