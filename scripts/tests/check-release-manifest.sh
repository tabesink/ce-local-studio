#!/usr/bin/env bash
# Adversarial / fixture altitude for P12-06 release-manifest check (no Docker/Syft).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT/app"
exec python -m pytest tests/test_release_manifest.py -q --tb=line
