from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

PINNED_LIGHTRAG_VERSION = "1.4.16"
VENDORED_LIGHTRAG_PACKAGE_DIR = Path(__file__).resolve().parents[2] / "vendor" / "lightrag"
VENDORED_LIGHTRAG_IMPORT_ROOT = VENDORED_LIGHTRAG_PACKAGE_DIR.parent


def ensure_vendored_lightrag_import_path() -> Path:
    if not (VENDORED_LIGHTRAG_PACKAGE_DIR / "__init__.py").is_file():
        raise RuntimeError("Vendored LightRAG package is unavailable.")
    import_root = str(VENDORED_LIGHTRAG_IMPORT_ROOT)
    if import_root not in sys.path:
        sys.path.insert(0, import_root)
    return VENDORED_LIGHTRAG_PACKAGE_DIR


def purge_loaded_lightrag_modules() -> None:
    for module_name in tuple(sys.modules):
        if module_name == "lightrag" or module_name.startswith("lightrag."):
            del sys.modules[module_name]


def assert_vendored_lightrag_loaded(module: ModuleType) -> None:
    loaded_file = getattr(module, "__file__", None)
    if not loaded_file:
        raise AssertionError("LightRAG module has no loaded file.")
    loaded_path = Path(loaded_file).resolve()
    try:
        loaded_path.relative_to(VENDORED_LIGHTRAG_PACKAGE_DIR)
    except ValueError as exc:
        raise AssertionError("LightRAG did not load from the vendored package.") from exc
