# P10-05 Provider Packaging Inventory

Date: 2026-07-28

Owner: P10-05 / U1

Plan: `docs/plans/2026-07-28-012-feat-p10-05-provider-packaging-plan.md`

Status: inventory complete; U2 packaging gates landed (live+parsers image args; `embeddings` extra)

## Boundary

Inventory only. Records current packaging, image, CI, and smoke seams for
Docling/Reducto parsers and OpenAI/Bedrock/Ollama embedding/synthesis providers.
Does not change code, claim production support, or install network providers into
default verify.

Adjacent seams (not owned here): P10-04 `object-store` extra /
`CE_STACK_OBJECT_STORE_IMAGE`; P5-04 live LightRAG topology /
`CE_STACK_LIVE_IMAGE`.

## Disposition key

| Disposition | Meaning |
| --- | --- |
| retain-and-reverify | Keep seam; prove under P10-05 units |
| modify | Change packaging/binding/behavior in this slice |
| add | New packaging gate, matrix, smoke, or adapter |
| remove-from-phase-1 | Not Phase 1 |

## Closed tech-stack kinds

| Kind | Role | Tech-stack status |
| --- | --- | --- |
| Docling | local document parser | supported |
| Reducto | external document parser | supported |
| OpenAI | synthesis + embedding candidate | supported egress |
| AWS Bedrock | synthesis + embedding candidate | supported egress |
| Ollama | synthesis + embedding candidate | local-only egress |

## pyproject extras (current)

| Extra | Packages | Image/CI ownership today |
| --- | --- | --- |
| (default) | FastAPI stack only | default `app/Dockerfile` / default Compose / root verify |
| `lightrag-runtime` | numpy, json-repair, dotenv, networkx, nano-vectordb, tiktoken, httpx, aiohttp | `CE_STACK_LIVE_IMAGE=1` |
| `object-store` | boto3 | `CE_STACK_OBJECT_STORE_IMAGE=1` (P10-04) |
| `parsers` | docling, reductoai | **declared but not installed by any Dockerfile gate** |
| `synthesis` | openai | **declared but not installed by any Dockerfile gate** |
| `test` | pytest, httpx, ruff | local/CI test installs |

No dedicated `embeddings` extra exists. Bedrock/Ollama SDKs are absent from
`pyproject.toml`. Embedding calls today are synthetic inside
`context_engine/tools/ce_lightrag_shim.py`.

## Image / Compose ownership matrix

| Concern | Owning process/image | Current seam | P10-05 disposition |
| --- | --- | --- | --- |
| Docling / Reducto SDKs | stack API + worker image | `parsers` extra unused by Dockerfile | **add** image gate (e.g. `CE_STACK_PARSERS_IMAGE`) + install in worker/API profiles that claim parsers |
| OpenAI synthesis SDK | stack API + worker image | `synthesis` extra unused by Dockerfile | **add**/wire into worker/API profile that claims synthesis |
| Embedding provider SDKs | private per-domain LightRAG runtime image | synthetic embed in shim; no provider extras on runtime image | **add** runtime embedding extras/bindings; keep out of browser/BFF |
| LightRAG vendored runtime | per-domain container via live overlay | `lightrag-runtime` + `CE_STACK_LIVE_IMAGE` | retain-and-reverify (P5-04 topology) |
| Object store (S3/MinIO) | API/worker | `object-store` + MinIO overlay | retain-and-reverify (P10-04); staging altitude for U4/U8 |
| Browser / BFF | frontend image | no parser/provider SDKs | retain — must stay free of provider SDKs |

## Adapter / runtime reality

| Seam | Path | Current behavior | Disposition |
| --- | --- | --- | --- |
| Parser port | `adapters/parsers.py` | Docling in-process convert; Reducto transport with timeout; URL `type=url` fail-closed; `PreparedSource` anti-corruption | **modify** (U6): killable Docling; private URL/asset resolve |
| Synthesis registry | `adapters/synthesis.py` | OpenAI live adapter; Bedrock/Ollama `UnsupportedSynthesisAdapter` | retain-and-reverify OpenAI; Bedrock/Ollama stay fail-closed until smoke |
| Embedding | `tools/ce_lightrag_shim.py` | Deterministic synthetic vectors; stub LLM `"entity"` | **modify** (U7): closed real adapters from sealed profile |
| Sealed credentials | runtime `provider.env` | Loaded into shim env with permission check | retain-and-reverify; extend for embedding kind/model/credential |
| Index/query profile | `TrustedRuntimeResolver` / indexing services | Frozen domain embedding profile dimensions/model | retain-and-reverify; bind to real adapter |

## CI / evidence altitude

| Lane | Network providers | Object store | Parser/embed proof today | Target after P10-05 |
| --- | --- | --- | --- | --- |
| Root `scripts/verify.sh` / default Compose | none | filesystem | fixture/injected parser dicts; synthetic embed in local LightRAG path | unchanged: no-network fixtures only |
| Opt-in live LightRAG (`compose.stack.live.yml`) | none required for topology | filesystem default | handcrafted Source Block → submit/ready/retrieve (P5-04) | retain topology credit; not full pipeline |
| Opt-in MinIO (`compose.stack.minio.yml`) | none | S3/MinIO | object-store readiness/recon (P10-04) | staging altitude for production-store claims |
| Credential-gated provider staging (new) | explicit gate + secrets | filesystem or MinIO per profile label | absent | **add** U4/U8 scripts + evidence |

## Kind × packaging × support draft

Statuses below are **inventory**, not production claims. Production-supported
requires U4/U8 smoke evidence (KTD1).

| Kind | Packaged in pyproject | Installed in claimed image | Fixture proof | Live smoke | Full pipeline | Draft status |
| --- | --- | --- | --- | --- | --- | --- |
| Docling | `parsers` extra | no (gap) | yes (injected) | no | no | packaged-declared / fail-closed until smoke |
| Reducto | `parsers` extra | no (gap) | yes (injected); URL unresolved | no | no | packaged-declared / fail-closed until smoke |
| OpenAI synthesis | `synthesis` extra | no (gap) | yes (injectable transport) | stack smoke allows unready terminal | no | fixture-proven; image packaging open |
| Bedrock synthesis | none | no | fail-closed registry | no | no | fail-closed |
| Ollama synthesis | none | no | fail-closed registry | no | no | fail-closed |
| OpenAI embedding | none | no | synthetic only | no | no | **add** packaging + binding |
| Bedrock embedding | none | no | none | no | no | fail-closed until catalog+smoke |
| Ollama embedding | none | no | none | no | no | fail-closed until catalog+smoke |

## Call-site inventory (brownfield)

| Call site | Notes | Disposition |
| --- | --- | --- |
| `default_parser_registry` / prep worker | Uses Docling/Reducto adapters when parser_kind set | modify via U6 |
| `_default_docling_convert` | In-process; maps TimeoutError; no killable deadline | modify |
| `_default_reducto_transport` / `_reducto_result_to_payload` | URL results raise malformed | modify |
| `ce_lightrag_shim.embed` | Synthetic numpy vectors | modify |
| `ce_lightrag_shim.llm` | Stub `"entity"` | modify (production path) |
| `default_synthesis_registry` | OpenAI + unsupported Bedrock/Ollama | retain-and-reverify |
| `app/Dockerfile` RUN extras | live / object-store only | modify (U2) |
| Compose overlays | live + minio; no parsers overlay | add runbook/matrix notes; optional build-arg |

## Explicit non-goals (this inventory)

- Browser-selectable providers
- New provider kinds beyond tech-stack list
- Claiming Bedrock/Ollama production support without smoke
- Installing parser/provider SDKs into default CI images
- Replacing P5-04 topology tests with full-pipeline proof (complement, KTD8)

## Next units

| Unit | Consumes this inventory |
| --- | --- |
| U2 | Close pyproject/image gaps for parsers + embedding/synthesis extras |
| U6 | Docling killable timeout; Reducto URL/asset resolve; fixtures |
| U7 | Real embedding adapters in LightRAG runtime from sealed profile |
| U3 | Operator matrix from kind × status table |
| U4/U8 | Credential-gated staging + full upload→Evidence path |
| U5 | Evidence + tracker DONE |

## Residual for later owners

| Item | Owner |
| --- | --- |
| Combined live.yml + minio.yml three-file matrix | P12-04 (unless trivial here) |
| Immutable artifact digests / SBOM for parser/provider pins | P12-06 |
| Browser/capacity failure on real pipeline | P12-07 |
| Production acceptance | P12-08 |
