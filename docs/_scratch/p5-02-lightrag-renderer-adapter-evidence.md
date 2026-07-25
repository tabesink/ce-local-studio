# P5-02 Versioned Canonical-Block Renderer and Vendored LightRAG Adapter Evidence

Date: 2026-07-25

Slice: P5-02

Requirements: FR-05; A-08 handoff/provenance half; DRIFT-27 timeout half;
versioned LightRAG handoff with local provenance markers.

Status: DONE - implemented and proven 2026-07-25

## Implemented and retained behavior

- `LIGHTRAG_HANDOFF_SCHEMA_VERSION = "1"` pins the handoff envelope.
- `render_blocks_to_lightrag_handoff` emits
  `[CE_SOURCE schema=1 …]` plus ordered `[CE_BLOCK id=… order=…]` markers,
  stable SHA-256 content hash, and rejects empty/duplicate/blank blocks.
- `render_lightrag_input` loads ordered Source Blocks and delegates to the
  pure renderer.
- `LocalLightRAGIndexClient` proves idempotent submit (same request/hash),
  content-hash conflict, readiness, delete/absence, and preserved block-id
  provenance under a per-domain runtime directory.
- Native `LightRAGClient._run` bounds lifecycle work with
  `CE_SOURCE_INDEX_TIMEOUT_SECONDS` (default 120) via `asyncio.wait_for` and
  maps overrun to safe `504 source_index_timeout` (DRIFT-27 timeout half).
  Cancel/cleanup under the process lock is also budgeted (2s) so hangy finalize
  cannot retain the lock indefinitely.
- Defaults keep `CE_SOURCE_INDEX_LEASE_SECONDS` (180) strictly greater than the
  index timeout (120), mirrored by Settings fail-closed validation.
- Process-wide native lifecycle lock retained until per-domain concurrency is
  separately proven.

## Proof-first evidence

1. Red collection baseline: missing `LIGHTRAG_HANDOFF_SCHEMA_VERSION` /
   `render_blocks_to_lightrag_handoff` import from
   `tests/test_lightrag_renderer_adapter.py`.
2. Green unit suite: renderer markers/hash/rejection; local adapter
   idempotent submit/conflict/readiness/delete/provenance; native timeout
   fail-closed without stack leakage.

## Verification

```text
cd app
python -m pytest tests/test_lightrag_renderer_adapter.py -q
# 5 passed
```

## Residuals / deferred

- Admin index submit/poll/retry/cancel/delete HTTP + eligibility → P5-03.
- Native uncertain-outcome reconciliation and heartbeat during long submit →
  P5-03 (DRIFT-32 index / DRIFT-28 remainder).
- Removing native process-wide lifecycle lock after per-domain concurrency
  proof.
- Full native integration against real embedding/LLM providers remains
  Compose/local-client for Phase 1 smoke; native uses synthetic stubs.
