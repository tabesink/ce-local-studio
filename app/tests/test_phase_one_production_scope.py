from __future__ import annotations

import json
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent
BACKEND_ROOT = APP_ROOT / "context_engine"
CLIENT_SOURCE_ROOT = APP_ROOT / "client" / "src"
CLIENT_ROUTE_ROOT = CLIENT_SOURCE_ROOT / "app"

DEFERRED_MARKERS = (
    "/admin/audit-events",
    "/admin/wiki",
    "/diagnostics/lightrag",
    "/logs",
    "/wiki",
    "logs-observability",
    "ref_kind = \"wiki\"",
    "ref_kind = 'wiki'",
    "wiki_page",
    "wiki_revision",
)
PRODUCTION_FILES = (
    APP_ROOT / "pyproject.toml",
    APP_ROOT / "Dockerfile",
    APP_ROOT / "compose.stack.yml",
    APP_ROOT / ".env.stack.example",
    APP_ROOT / "client" / "package.json",
    APP_ROOT / "client" / "Dockerfile",
    APP_ROOT / "contracts" / "openapi.json",
    REPO_ROOT / "scripts" / "generate_openapi.py",
    REPO_ROOT / "scripts" / "dev.sh",
)


def test_phase_one_physical_route_tree_is_exact() -> None:
    route_directories = {path.name for path in CLIENT_ROUTE_ROOT.iterdir() if path.is_dir()}

    assert route_directories == {
        "chat",
        "database-visualize",
        "documents",
        "forbidden",
        "login",
        "settings",
    }


def test_phase_one_active_source_and_build_manifests_exclude_deferred_markers() -> None:
    source_files = (
        *BACKEND_ROOT.rglob("*.py"),
        *CLIENT_SOURCE_ROOT.rglob("*.ts"),
        *CLIENT_SOURCE_ROOT.rglob("*.tsx"),
        *PRODUCTION_FILES,
    )

    for path in source_files:
        text = path.read_text(encoding="utf-8").casefold()
        assert not any(marker.casefold() in text for marker in DEFERRED_MARKERS), path


def test_generated_openapi_excludes_deferred_operations() -> None:
    document = json.loads((APP_ROOT / "contracts" / "openapi.json").read_text(encoding="utf-8"))

    assert not any(
        path.startswith("/api/v1/wiki")
        or path.startswith("/api/v1/admin/wiki")
        or path == "/api/v1/admin/audit-events"
        or "/diagnostics/" in path
        for path in document["paths"]
    )


def test_active_package_has_no_compiled_deferred_modules() -> None:
    compiled_names = {path.name.casefold() for path in BACKEND_ROOT.rglob("*.pyc")}

    assert not any(name.startswith(("diagnostics.", "wiki.")) for name in compiled_names)
