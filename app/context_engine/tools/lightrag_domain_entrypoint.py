"""Private per-domain LightRAG shim entrypoint for Docker controller start."""

from __future__ import annotations

import os
import sys
from pathlib import Path

RUNTIME_ROOT = Path("/ce-runtime")
SECRETS_FILE = RUNTIME_ROOT / "secrets" / "provider.env"
WORKING_DIR = RUNTIME_ROOT / "lightrag"
DEFAULT_PORT = "9621"


def _load_sealed_env() -> None:
    if not SECRETS_FILE.is_file():
        return
    mode = SECRETS_FILE.stat().st_mode & 0o777
    if mode & 0o077:
        print("Sealed provider env permissions are too open.", file=sys.stderr)
        raise SystemExit(1)
    for raw_line in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


def main() -> int:
    _load_sealed_env()
    WORKING_DIR.mkdir(parents=True, exist_ok=True)
    (RUNTIME_ROOT / "workspace").mkdir(parents=True, exist_ok=True)
    (RUNTIME_ROOT / "logs").mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("HOST", "0.0.0.0")
    os.environ.setdefault("PORT", DEFAULT_PORT)
    os.environ.setdefault("WORKING_DIR", str(WORKING_DIR))
    os.environ.setdefault("CE_RUNTIME_ROOT", str(RUNTIME_ROOT))
    os.chdir(str(RUNTIME_ROOT))

    from context_engine.tools.ce_lightrag_shim import main as shim_main

    shim_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
