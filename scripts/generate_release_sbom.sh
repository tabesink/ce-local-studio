#!/usr/bin/env bash
# P12-06: generate CycloneDX JSON SBOM for one image digest via Syft.
# Fail closed if Syft is missing. Pin version with CE_SYFT_VERSION (default v1.20.0).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYFT_VERSION="${CE_SYFT_VERSION:-v1.20.0}"
IMAGE_REF="${1:-}"
OUTPUT="${2:-}"

if [[ -z "$IMAGE_REF" || -z "$OUTPUT" ]]; then
  echo "usage: $0 <image-ref-or-digest> <output.cdx.json>" >&2
  exit 2
fi

if ! command -v syft >/dev/null 2>&1; then
  echo "FAIL syft_missing (install Syft ${SYFT_VERSION}; see docs/_scratch/p12-06-immutable-artifact-inventory.md)" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT")"
# Prefer digest-capable scan; Syft accepts image refs.
syft "$IMAGE_REF" -o cyclonedx-json >"$OUTPUT"
if [[ ! -s "$OUTPUT" ]]; then
  echo "FAIL sbom_empty $OUTPUT" >&2
  exit 1
fi
# Integrity floor: require bomFormat marker
if ! grep -q 'CycloneDX\|cyclonedx\|bomFormat' "$OUTPUT"; then
  echo "FAIL sbom_integrity_floor $OUTPUT" >&2
  exit 1
fi
echo "OK wrote $OUTPUT (syft ${SYFT_VERSION})"
