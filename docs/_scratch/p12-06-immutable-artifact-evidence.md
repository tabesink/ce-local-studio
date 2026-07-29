# P12-06 Immutable Artifact Manifest Evidence

Date: 2026-07-28  
Status: DONE at unit + PR-light altitude; release-full live Syft×built-image digests residual (operator)  
Plan: `docs/plans/2026-07-28-014-feat-p12-06-immutable-artifact-manifest-plan.md`  
Inventory: `docs/_scratch/p12-06-immutable-artifact-inventory.md`  
Branch: `feat/p12-06-immutable-artifact-manifest`

## Prerequisites cited

| Prerequisite | Evidence |
| --- | --- |
| P5-04 | `docs/_scratch/p5-04-lightrag-real-runtime-evidence.md` |
| P10-04 | `docs/_scratch/p10-04-minio-object-store-evidence.md` |
| P10-05 | `docs/_scratch/p10-05-provider-packaging-evidence.md` |
| P10-06 | `docs/_scratch/p10-06-governed-preview-evidence.md` |
| P12-02 | `docs/_scratch/p12-02-suite-contract-convergence-evidence.md` |

## Delivered

| Unit | Artifact |
| --- | --- |
| U1 | `docs/_scratch/p12-06-immutable-artifact-inventory.md` |
| U2 | `docs/releases/release-manifest.schema.json`, `app/scripts/generate_release_manifest.py`, `docs/releases/release-manifest.json` (PR profile) |
| U3 | Provenance allowlist + SBOM binding in generator; `scripts/generate_release_sbom.sh` (fail-closed if Syft missing); fixture CDX under `docs/_scratch/p12-06-release-fixtures/` |
| U4 | `--check` mode; `scripts/check-release-manifest.sh`; PR-light hooks in `scripts/verify.sh`; unit/adversarial via `scripts/tests/check-release-manifest.sh` |
| U5 | This evidence; tracker + brownfield updates |

## Commands and results

### Unit tests (AE1/AE2 altitude)

```bash
cd app
python -m pytest tests/test_release_manifest.py -q
```

Observed (2026-07-28): **13 passed**.

### PR-light generate + check

```bash
cd app
python -m scripts.generate_release_manifest --profile pr --output ../docs/releases/release-manifest.json
python -m scripts.generate_release_manifest --profile pr --check ../docs/releases/release-manifest.json
```

Observed: **OK**.

### Fixture release-full wiring (not production digests)

```bash
# Produces docs/_scratch/p12-06-release-fixtures/release-manifest.release-fixture.json
# with synthetic digests + fixture CycloneDX — proves schema/SBOM/provenance wiring only.
```

Observed: fixture manifest written. Digests are **not** release authority.

### Syft / live image matrix

| Probe | Result |
| --- | --- |
| Docker client | Present (27.2.0) |
| Syft on PATH | **Absent** — `scripts/generate_release_sbom.sh` fails closed (`syft_missing`) |
| Live release-full build→Syft→verify | **Residual** — operator installs Syft `CE_SYFT_VERSION=v1.20.0`, builds web + controller with all `CE_STACK_*=1`, replaces fixture digests under `docs/releases/` |

## Acceptance examples

| AE | Result | Altitude |
| --- | --- | --- |
| AE1 | PASS | Unit + fixture release generate |
| AE2 | PASS | Unit (mutate digest/lock/schema/SBOM hash/stub controller) |
| AE3 | PARTIAL | Fixture/mock Syft wiring PASS; live Syft×built digest residual |
| AE4 | PASS | Prerequisites cited; packaging ≠ production-supported; P12-04 drill digests non-claims |

## Non-claims

- Fixture digests (`sha256:aaa…` / `bbb…`) are **not** production or local-production release pins.
- P12-04 Compose-matrix drill digests are **not** this manifest.
- Packaging pins do **not** elevate kinds to `production-supported`.
- No product SBOM UI.
- No cosign / registry promotion (P12-08).
- LibreOffice/PPT not in required pin set.
- Default CI remains lean; release-full not absorbed into Docker-less PR path beyond PR-light pin check.

## Privacy checklist

- Provenance allowlist only (`gitSha`, dirty, builtAt, ciRunId, tool versions, digests, SBOM/lock hashes, `CE_STACK_*` gates).
- Deny-pattern scan in validate path.
- No credentials, runtime URLs, or host paths in committed PR manifest or fixture (spot-checked).

## Residuals → owners

| Residual | Owner |
| --- | --- |
| Live Syft×built web/controller digests + real `*.cdx.json` under `docs/releases/` | Operator / release job (blocks claiming production digests) |
| Cosign / keyless / Rekor / registry promotion | P12-08 |
| Multi-arch beyond `linux/amd64` | P12-08 / ops |
| Dedicated GHA release-full workflow | Optional; operator command documented |
| Support-label elevation via live smoke | ops / P12-08 |

## Operator release-full command (residual until Syft + builds)

```bash
# 1) Build release controller (all gates) + web image; docker image inspect > inspect JSON
# 2) Resolve MinIO/mc digests (docker pull + inspect)
# 3) CE_SYFT_VERSION=v1.20.0 bash scripts/generate_release_sbom.sh <ref> docs/releases/web.cdx.json
# 4) Same for controller digest → docs/releases/controller.cdx.json
# 5) cd app && python -m scripts.generate_release_manifest --profile release \
#      --assert-release-gates \
#      --web-inspect ... --controller-inspect ... --controller-ref context-engine-live:<tag> \
#      --minio-digest sha256:... --mc-digest sha256:... --postgres-digest sha256:... \
#      --sbom sha256:...=../docs/releases/web.cdx.json \
#      --sbom sha256:...=../docs/releases/controller.cdx.json \
#      --output ../docs/releases/release-manifest.json
# 6) python -m scripts.generate_release_manifest --profile release --check ../docs/releases/release-manifest.json
```

Review follow-up (same branch): release `--check` compares regeneratable pins; empty `--controller-ref` fails; `--assert-release-gates` required for release profile; Syft script fails closed on version mismatch; dirty check honors `--allow-dirty-release`.

## Tracker

P12-06 → DONE (unit + PR-light; live Syft digests residual). P12-08 consumes committed schema/generator and replaces fixture with real digests before go/no-go.
