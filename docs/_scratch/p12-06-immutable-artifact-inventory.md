# P12-06 Immutable Artifact Manifest Inventory

Date: 2026-07-28  
Owner: coding agent (P12-06)  
Status: U1 inventory complete — pin field → source → profile matrix frozen  
Plan: `docs/plans/2026-07-28-014-feat-p12-06-immutable-artifact-manifest-plan.md`  
Authority: `docs/quality/definition-of-done.md` production release gate; `docs/architecture/deployment-topology.md` release sequence step 1; `docs/master-build-plan.md` P12-06.

## Disposition legend

| Value | Meaning |
| --- | --- |
| `retain` | Already correct; keep as pin source |
| `modify` | Change in this slice |
| `add` | New script/schema/test/doc in this slice |
| `credit` | Proven elsewhere; cite — do not re-own |
| `defer` | Explicit residual (other P12 / ops) |
| `reject` | Must not enter release authority |

## Prerequisites (DONE — cite, do not re-prove)

| Prerequisite | Evidence | What P12-06 consumes |
| --- | --- | --- |
| P5-04 real private LightRAG runtime | `docs/_scratch/p5-04-lightrag-real-runtime-evidence.md` | Vendored LightRAG 1.4.16; live controller image (not Alpine); SBOM residual → here |
| P10-04 MinIO object store | `docs/_scratch/p10-04-minio-object-store-evidence.md` | MinIO/mc Compose tags; object-store image gate |
| P10-05 provider packaging | `docs/_scratch/p10-05-provider-packaging-evidence.md` | Parser/provider extras + packaging ≠ production-supported |
| P10-06 governed preview | `docs/_scratch/p10-06-governed-preview-evidence.md` | Preview renderer IDs + `CE_STACK_PREVIEW_IMAGE`; renderer SBOM residual → here |
| P12-02 suite/contract convergence | `docs/_scratch/p12-02-suite-contract-convergence-evidence.md` | Contract freeze; SBOM/manifest deferred → here |

## Artifact paths (KTD1)

| Artifact | Path | Disposition |
| --- | --- | --- |
| Manifest schema | `docs/releases/release-manifest.schema.json` | `add` |
| Generated manifest | `docs/releases/release-manifest.json` | `add` |
| CycloneDX SBOMs | `docs/releases/*.cdx.json` | `add` |
| Generator | `app/scripts/generate_release_manifest.py` | `add` |
| SBOM helper | same module / `scripts/generate_release_sbom.sh` | `add` |
| Verify | `scripts/check-release-manifest.sh` (+ Python check mode) | `add` |
| Reject `app/contracts/` for release pins | — | `reject` — ops/release evidence, not browser API contracts |

## Role → digest map (Compose reality)

| Role | Compose / runtime source | Typical digest identity | Disposition |
| --- | --- | --- | --- |
| `web` | `app/client/Dockerfile` → frontend image | Distinct | `add` pin |
| `api` | `CE_DOMAIN_CONTROLLER_IMAGE` / live overlay (`compose.stack.live.yml`) | Shared controller | `add` pin |
| `worker` | same live image as api | **Same digest as api** when Compose shares image | `add` role map |
| `lightragRuntime` | Domain containers from `CE_DOMAIN_CONTROLLER_IMAGE` | **Same digest as api** | `add` role map |
| Placeholder controller | `alpine:3.20` (`domain_runtime_controller.PLACEHOLDER_IMAGE`, default config) | Must fail release-full | `reject` as release pin |

Release app image authority (KTD9): `app/Dockerfile` with all gates `1`:
`CE_STACK_LIVE_IMAGE`, `CE_STACK_PARSERS_IMAGE`, `CE_STACK_OBJECT_STORE_IMAGE`, `CE_STACK_PREVIEW_IMAGE`.  
Default slim CI image is **not** release authority (`reject`).

## Pin field register

| DoD / topology field | Source | PR-light | Release-full | Disposition |
| --- | --- | --- | --- | --- |
| Manifest `schemaVersion` | generator constant | required | required | `add` |
| Source git SHA + dirty | `git rev-parse` / dirty detect | required | required; dirty fail | `add` |
| Platform | `linux/amd64` (KTD5) | record | required | `add` |
| Web image digest | `docker image inspect` | omit | required | `add` |
| api/worker/lightragRuntime digests | inspect + role map | omit | required (shared OK) | `add` |
| MinIO tag+digest | `app/compose.stack.minio.yml` tag → inspect/resolve | tag OK | digest required | `retain` tag + `add` digest |
| mc tag+digest | same overlay | tag OK | digest required | `retain` + `add` |
| postgres pin | `app/compose.stack.yml` `postgres:16` | tag | digest preferred; tag-only residual named if unresolved | `add` / residual OK |
| `app/uv.lock` sha256 | file hash | required | required | `add` |
| `app/client/package-lock.json` sha256 | file hash | required | required | `add` |
| Alembic head | `SUPPORTED_ALEMBIC_HEAD` in `app/context_engine/services/readiness.py` | required | required | `retain` |
| OpenAPI / API version | `API_VERSION` in `app/context_engine/api/contract_app.py` (`0.1.0`) | required | required | `retain` |
| SSE schema version | `TURN_EVENT_SCHEMA_VERSION` in `app/context_engine/models.py` (`1.0`) | required | required | `retain` |
| LightRAG pin | `PINNED_LIGHTRAG_VERSION` in `app/context_engine/services/lightrag_runtime.py` + `app/vendor/lightrag/_version.py` | version string | version + non-placeholder controller digest | `retain` + `add` |
| Image gates | Dockerfile ARGs / release build record | constants present | all four `1` | `add` |
| Parser/provider packages | versions from `app/uv.lock` for release extras (docling, reductoai, openai, …) | optional | required versions; **no** `production-supported` field | `credit` packaging + `add` pin |
| Renderer IDs | `ce-preview-v1`, `ce-preview-text-v1`, `ce-preview-pdf-passthrough-v1` in `app/context_engine/adapters/preview_renderer.py` | optional | required | `retain` |
| SBOM path + sha256 | Syft CycloneDX per **distinct** digest | omit | required | `add` |
| Provenance allowlist | git SHA, dirty, build UTC, optional CI id, tool versions, digests, SBOM/lock hashes, `CE_STACK_*` 0/1 only | omit/minimal | required | `add` |
| Generator / Syft version | pinned in inventory/evidence | record when used | required for SBOM | `add` |
| P12-04 drill digests | `stack_image_rollback_drill` / backup consistency | — | **reject** as release pins | `reject` / `credit` helpers only |
| Cosign / registry | — | — | — | `defer` → P12-08 |
| Multi-arch beyond amd64 | — | — | — | `defer` |
| LibreOffice / PPT | casual pyproject note | — | — | `reject` from required pin set |
| Product SBOM UI | — | — | — | `reject` |
| Support-label elevation | `docs/operations/provider-deployment-profiles.md` | — | pins never elevate | `credit` honesty |

## Syft pin

| Item | Value | Disposition |
| --- | --- | --- |
| Tool | Syft | `add` |
| Format | CycloneDX JSON | `add` |
| Version pin | Document in evidence at first release-full run; env `CE_SYFT_VERSION` (default recorded in generator) | `add` |
| Mandatory subjects | Each **distinct** digest in role map (web + unique controller) | `add` |
| MinIO/mc SBOM | Not generated locally | `reject` fake local SBOM |

## Profile field matrix

**PR-light:** `schemaVersion`, git SHA (+ dirty warn), lock digests, Alembic head, API/SSE versions, LightRAG version strings, MinIO/mc/postgres **tags**, Dockerfile gate constant presence, `profile: pr`.

**Release-full:** PR-light + role→digest map @ `linux/amd64`, MinIO/mc digests, postgres digest or named residual, image gates all `1`, package versions, renderer IDs, SBOM paths+hashes, allowlisted provenance, Syft version, `profile: release`. Dirty tree fails.

Default `scripts/verify.sh` / PR `verify.yml`: PR-light only (or opt-in). Release-full: operator command / dedicated job; omission of GHA wiring is residual if operator command proven (KTD10 still requires one recorded release-full run for DONE).

## Credit helpers (non-release truth)

| Helper | Path | Use |
| --- | --- | --- |
| `parse_image_inspect_digest` | `app/scripts/stack_image_rollback_drill.py` | Reuse for inspect JSON |
| Consistency / drill digests | P12-04 capture / rollback records | **Not** release pins |

## Residuals

| Item | Owner |
| --- | --- |
| Cosign / keyless / Rekor / registry promotion | P12-08 |
| Multi-arch indexes | P12-08 / ops |
| Operator live digests elevating `production-supported` | ops / P12-08 (pins alone never elevate) |
| Vuln scan (Trivy/Grype) | optional later gate |
| GHA release-full workflow wiring | OK residual if operator command + evidence run exist |
| Compose live backup matrix digests | P12-04 residual (≠ release) |
