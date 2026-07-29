#!/usr/bin/env bash
# P12-06: verify release/pr manifest integrity (PR-light by default).
# Release-full digests/SBOM require a previously generated release profile
# manifest; this hook does not build images or invoke Syft.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="${CE_RELEASE_MANIFEST_PROFILE:-pr}"
MANIFEST="${CE_RELEASE_MANIFEST_PATH:-$ROOT/docs/releases/release-manifest.json}"

cd "$ROOT/app"
exec python -m scripts.generate_release_manifest --profile "$PROFILE" --check "$MANIFEST"
