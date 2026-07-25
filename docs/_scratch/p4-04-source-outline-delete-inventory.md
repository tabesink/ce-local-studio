# P4-04 Source Outline / Operation / Retry / Cancel / Delete Inventory

Date: 2026-07-25

Owner: P4-04

Status: DONE - implemented and proven 2026-07-25

Requirements and cases: FR-04; FR-08; A-07; A-09; M-11 redaction hook;
DRIFT-29; `http-api-catalog` source outline/operations/retry/cancel/delete;
`dto-schema-catalog` Outline items + `OperationDto`.

## Scope

- Close admin outline to `{kind,label,level,pageNumber}` with no canonical text.
- Project source operations as closed `OperationDto` (`targetKind: "source"`)
  and return `nextCursor` on the operations list.
- Cancel requires `If-Match` on source version; bump source/op versions on
  retry/cancel/delete; return strong `ETag` on mutation responses.
- Replace sync HTTP `204` delete with `202 {operation}`: one transaction fences
  the source (`state=deleting`), cancels active prep, redacts turns, expires
  live composer source tokens, queues a `delete` operation, and audits intent.
- Leased `SourceDeleteWorker` performs index/object cleanup and final row
  removal under preparation-generation fence (DRIFT-29 dual-write fix).
- Extend `source_preparation_operations.operation_type` to `prepare|delete`.

## Out of scope

- Index retry/cancel envelope closure beyond existing pilot (P5).
- Member document/content routes (P6/P9).
- HTTP `Idempotency-Key` transport (no shared helper yet; same residual as
  domain delete; durable op `request_id` remains).
- Full composer one-use consume races (P11).
- Production object-store vendor selection.

## Disposition register

| Surface | Current evidence | Disposition | P4-04 action |
| --- | --- | --- | --- |
| `source_outline` field shape | Private-ish keys; includes text blocks | replace | Closed outline items only |
| `safe_source_operation` | Flat non-OperationDto | replace | Mirror `safe_domain_operation` |
| Operations list | Missing `nextCursor` | modify | Add null cursor like domains |
| Cancel route | No If-Match | modify | `parse_if_match_version` + stale_revision |
| `delete_source` sync 204 + object-before-commit | DRIFT-29 / P4-03 residual | replace | Queue delete op + worker cleanup |
| Prep op type CHECK `prepare` only | Schema | modify | Add `delete` |
| Audit `source.deleted` only | Sync delete | modify | Add queued/succeeded/failed; keep deleted allowlisted |
| `purge_domain_sources_local` dual-write | Domain worker path | modify | Fence commit before object/row cleanup |
| `_redact_turns` always commits | Blocks atomic fence | modify | `commit=` flag for enqueue path |
| Worker loop | Domain delete only | modify | Source delete before domain delete |

## Retained invariants

- Parser kind frozen at upload; retry does not re-read runtime defaults.
- Prep publish remains lease/generation fenced (P4-03).
- One active source operation (prepare or delete) via partial unique index.
- Object keys / hashes / canonical markdown never appear in public DTOs.
- Delete cleanup retry must not undo redaction or restore query eligibility.

## Gaps closed by task-owned evidence

1. Unit: outline DTO privacy, OperationDto projection, If-Match parse wiring.
2. PostgreSQL: A-07 cancel generation fence; A-09 fence+redact+token expiry
   before object removal; worker cleanup reclaim; failed cleanup leaves
   `deleting` + retryable op.
3. HTTP: outline/operations/retry/cancel/delete status + closed envelopes +
   ETag/428/409; regenerate OpenAPI/TypeScript.
