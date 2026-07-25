# P5-02 Versioned Canonical-Block Renderer and Vendored LightRAG Adapter Inventory

Date: 2026-07-25

Owner: P5-02

Status: DONE - implemented and proven 2026-07-25

Requirements and cases: FR-05; A-08 handoff/provenance half; DRIFT-27
timeout/isolation half; `docs/architecture/data-and-lifecycle.md` LightRAG
index port; AGENTS.md versioned handoff with local provenance markers.

## Scope

- Pin the versioned canonical-block → LightRAG handoff renderer (`schema=1`)
  with stable `CE_SOURCE` / `CE_BLOCK` provenance markers and content-hash
  identity.
- Prove the local (Compose/dev) LightRAG index adapter: idempotent submit,
  readiness, delete/absence, and preserved block-id provenance — without
  network.
- Bound the native vendored LightRAG adapter lifecycle with a configured
  timeout and safe `source_index_timeout` mapping (DRIFT-27 timeout half).
- Keep per-domain working directories via the runtime controller / domain
  runtime root (isolation boundary).

## Out of scope

- Admin index submit/poll/retry/cancel/delete HTTP envelopes (P5-03).
- Query-eligibility service and member retrieval mapping (P5-03 / P6).
- Persisted readiness backoff and fair queue scheduling (DRIFT-28 remainder).
- Uncertain remote outcome reconciliation for native submit (DRIFT-32 index).
- Full native integration suite against real embedding/LLM providers
  (Compose stays on `CE_LIGHTRAG_CLIENT_KIND=local`; native uses synthetic
  embed/LLM stubs with timeout proof).
- Removing the process-wide native lifecycle lock before per-domain
  concurrency is separately proven.

## Disposition register

| Surface | Current evidence | Disposition | P5-02 action |
| --- | --- | --- | --- |
| `render_lightrag_input` handoff | Lifted `schema=1` + CE markers; no unit proof | modify | Extract pure renderer helper; pin schema constant; unit fixtures |
| `LocalLightRAGIndexClient` | Filesystem per-domain index records | retain-and-reverify | Fixture proof: idempotent submit, readiness, delete, provenance |
| `LightRAGClient` native | Global lock, unbounded `_run` | modify | Add `source_index_timeout_seconds`; `wait_for` + safe timeout error |
| `LightRAGClientProtocol` | Present | retain-and-reverify | Keep closed submit/readiness/delete/is_absent/retrieve surface |
| Vendored pin `1.4.16` | `lightrag_runtime.py` | retain-and-reverify | Assert path still used; no public contract leak |
| Index HTTP / eligibility | Lifted pilot | defer | P5-03 |

## Adapter decision (approved for this slice)

1. **Local client** — development/Compose default evidence path. Stores
   provenance-marked chunks under the domain runtime directory. Proves
   idempotency and delete without vendored native lifecycle.
2. **Native client** — vendored LightRAG 1.4.16 behind the existing protocol.
   Synthetic embedding/LLM stubs remain; every lifecycle call is bounded by
   `CE_SOURCE_INDEX_TIMEOUT_SECONDS` and process-serialized. Fail closed on
   timeout/unavailable with safe codes only.
3. **CI** — unit fixtures never require network or a live LightRAG service.

## Retained invariants

- Provenance markers stay private; public DTOs never expose rendered handoff,
  block IDs as LightRAG IDs, or remote document IDs.
- Content hash + request id remain the stable submit identity.
- Adapters never authorize or mutate product index_state (workers/services do).
- Local and native clients share `LightRAGClientProtocol`.

## Gaps closed by task-owned evidence

1. Unit: renderer schema/markers/hash/rejection; local idempotent submit/
   conflict/readiness/delete/provenance; native timeout fail-closed.
2. Config: `CE_SOURCE_INDEX_TIMEOUT_SECONDS` documented in evidence.
