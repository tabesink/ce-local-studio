# P11-01 Composer Ref Schema Inventory

Date: 2026-07-27

Status: reconciled

Owner: P11-01

Authority: `docs/database-schema.txt` (`prompt_templates`, `composer_ref_tokens`,
`conversation_turn_composer_refs`); FR-07; M-09; DRIFT-26 / DRIFT-33.

## Retained

- Baseline tables from `724564649a13_baseline_phase_one_schema.py` plus
  accepted-ref `public_ref` from `d07141ac7d95_add_public_refs_and_cancelled_turns.py`.
- Closed `ref_kind` set: `source` | `evidence` | `template` only.
- Hash-only `composer_ref_tokens.token_hash` (length 64); no raw token column.
- Accepted-ref opaque `public_ref`, `ref_order >= 1`, redaction CHECK nulling
  safe labels, UNIQUE `(turn_id, ref_order)`.
- Owner FK CASCADE on tokens; turn FK CASCADE on accepted refs.
- Brownfield strengthenings that do not contradict the terse schema contract:
  unique template name; token hash length check; accepted-ref kind-target CHECK;
  extra private-link indexes (`source_document`, `evidence_ref`, `template`,
  `ref_kind`+`target_id`).

## Modified in P11-01

- No additive DDL required at inventory time. Models and Alembic head already
  reproduce the three-table invariants on PostgreSQL 16.
- Proof artifacts: metadata/closed-set tests and opt-in PostgreSQL constraint
  suite (`app/tests/test_postgres_composer_ref_schema.py`).

## Deferred

- Consume / `used_at` column and durable `already-consumed` seed rows → P11-02
  (DRIFT-26). Reserved unseeded fixture key: `token_mina_consumed_source`.
- Discover HTTP, token minting, ownership/expiry/domain/target validation → P11-02.
- Private assembly, turn `composer_ref_fingerprint` consistency with seeded
  accepted refs, replay/conflict → P11-03.
- `token` vs `refToken` catalog/runtime drift and max-ref catalog parity → P11-02.
- Invented FKs from accepted-ref private link columns to source/evidence/template
  tables (schema does not require them).

## Removed / excluded from Phase 1

- Wiki / publication composer kinds and columns (DRIFT-33 / P0-07 fence).
- Raw composer tokens in product tables.
- Assembled prompts / template bodies in public projections.

## Residual fixture key (unseeded)

| Key | Kind | Status |
| --- | --- | --- |
| `token_mina_consumed_source` | source | Reserved for P11-02 after consume-state schema |
