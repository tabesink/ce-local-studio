#!/usr/bin/env bash
# Adversarial / fixture altitude for P12-06 release-manifest check (no Docker/Syft).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT/app"
exec uv run --frozen --python 3.12 --extra test pytest tests/test_release_manifest.py -q --tb=line
