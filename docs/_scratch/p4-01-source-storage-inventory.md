# P4-01 Source Documents Schema, Opaque Refs, and Storage Adapter Inventory

Date: 2026-07-25

Owner: P4-01

Status: DONE - implemented and proven 2026-07-25

Requirements and cases: FR-04; document-and-evidence `documentRef`;
DTO `AdminSourceDto`; DRIFT-14 opaque-ref foundation; architecture
governed object-store port (stream put/get/range/delete, opaque keys).

## Scope

- Reverify `source_documents` / `source_preparation_operations` constraints on
  PostgreSQL 16 at the current Alembic head, then add optimistic `version`
  columns required by closed `AdminSourceDto` / `OperationDto`.
- Persist private `original_object_key` metadata so deletion/restore operates
  on one recorded consistency point (architecture object-store rule).
- Project closed `AdminSourceDto` from `safe_source`: `documentRef`,
  `displayName`, `sizeBytes`, `activeOperationId`, `version`,
  `allowedActions`; map internal index states to public `IndexState`; omit
  hashes, block keys, block/image counts, and index error detail.
- Extract governed object-store port with filesystem development adapter:
  opaque keys, put/get/range/delete, path-escape protection, idempotent
  delete. Wire source original bytes through the port.
- Strengthen `public_ref` generation to cryptographically random URL-safe
  values (`doc_` + token).

## Out of scope

- Streaming upload sniff/bomb/limit hardening and parser-kind freeze proof
  (P4-02 / DRIFT-13).
- Real Docling/Reducto adapter boundary and atomic blocks/images publish
  races (P4-03 / DRIFT-22 / DRIFT-30).
- Outline/retry/cancel/delete `202 {operation}` / ETag/If-Match API closure
  (P4-04 / DRIFT-29).
- Member `GET /documents*` routes and governed PDF range delivery
  (P4-01 foundation only; remainder with P6-02 / P9-03 / DRIFT-14).
- Collapsing private index-state CHECK vocabulary to public
  `processing`/`deleting` (P5 index worker; P4-01 projects only).
- Production cloud object-store vendor selection (architecture decision).

## Disposition register

| Surface | Current evidence | Disposition | P4-01 action |
| --- | --- | --- | --- |
| Baseline `source_documents` / prep ops + `public_ref` | Present; no dedicated PG proof | retain-and-reverify | Prove FKs/CHECKs/unique public_ref/domain hash/active prep |
| `source_documents.version` / prep `version` | Missing; DTO requires Version | add | Migration + ORM + schema.txt |
| `original_object_key` | Missing; bytes path-derived | add | Private column + write/read/delete via port |
| Inlined `SourceStorage` filesystem class | Path layout under `CE_SOURCE_STORAGE_ROOT` | replace | Object-store Protocol + filesystem adapter; thin source facade |
| Lifted `safe_source` projection | Private-shaped fields; no `documentRef` | replace | Closed `AdminSourceDto` projection + leak assertions |
| `public_ref` default `uuid.hex` | Unique present | modify | `secrets.token_urlsafe` URL-safe refs |
| Internal index_state CHECK vs public IndexState | Drift (`submitting`/`accepted`/…) | retain-and-reverify | Public mapping only; CHECK change deferred to P5 |
| Member document/content routes | Absent / unavailable | defer | P6-02 / P9-03 |
| Upload sniff/stream limits | Buffered pilot | defer | P4-02 |

## Retained invariants

- Domain-scoped SHA-256 uniqueness (`UNIQUE(domain_id, original_sha256)`).
- One active preparation operation per source (partial unique index).
- Parser kind frozen on the source row at upload (P4-02 hardens proof).
- Object keys, storage paths, and hashes never appear in public DTOs.
- Filesystem adapter remains development-only; production vendor is undecided.

## Gaps closed by task-owned evidence

1. Unit proofs for closed `AdminSourceDto` projection, index-state mapping,
   and object-store put/get/range/delete/path-escape/idempotent delete.
2. Disposable PostgreSQL 16 proof of schema versions, `public_ref` uniqueness,
   `original_object_key`, active-prep partial unique, and domain hash unique.
3. Upload writes an opaque object key and reads originals through the port
   without exposing keys in admin source projections.
