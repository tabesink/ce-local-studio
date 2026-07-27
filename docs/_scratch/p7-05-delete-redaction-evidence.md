# P7-05 Source and Domain Delete Redaction Evidence

Date: 2026-07-27

Owner: P7-05

Status: DONE

Requirements and cases: FR-08; M-11 chat/detail/SSE half; A-09; A-10;
R1–R11; AE1–AE7; KTD1–KTD7; DRIFT-29 chat-redaction half;
`docs/plans/2026-07-27-005-feat-delete-redaction-omission-plan.md`;
inventory `docs/_scratch/p7-05-delete-redaction-inventory.md`.

## Implemented boundary

- Inventory pinned retain/modify/defer before behavior edits.
- `redact_turns_for_domain` accepts `commit=` and redacts the dependent-turn
  union: `domain_rag` by `domain_id` plus evidence/composer-linked turns for
  every source in the domain (via `_dependent_turns_for_domain`).
- `enqueue_delete_domain` redacts dependent turns and expires source-kind and
  evidence-kind composer tokens inside the delete fence transaction (parity
  with `enqueue_delete_source`).
- `_expire_composer_tokens_for_source` also expires evidence-kind tokens whose
  `target_id` is an evidence ref for that source.
- P7-04 terminal/event fences retained: late `_complete_turn` /
  `_persist_event` cannot un-redact.
- Public omission proven for `safe_turn_dto`, sanitized ledger payloads,
  `turn.redacted` append, and redacted `terminalSnapshot`.

## Verification

### Focused non-PostgreSQL suite

```text
cd app
.\.venv\Scripts\python.exe -m pytest tests\test_delete_redaction.py -q
```

Expected: PASS (commit= deferral, idempotent redact, dependent-turn selection,
domain enqueue fence+token expiry, source-delete public omission + sentinel
absence, late-complete fence, terminal event block).

Local run (2026-07-27): `7 passed`.

### PostgreSQL 16 barrier suite (opt-in)

```text
cd app
$env:CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS='1'
$env:CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL='postgresql+psycopg://context_engine:context_engine@127.0.0.1:5438/postgres'
.\.venv\Scripts\python.exe -m pytest tests\test_postgres_delete_redaction_barriers.py -q
```

Covers source-delete enqueue redaction + DTO omission, domain-delete enqueue
redaction of running `domain_rag` turns, and late `_complete_turn` cannot
un-redact. Skips unless disposable-database opt-in is set.

Local run (2026-07-27) against `127.0.0.1:5438` disposable PostgreSQL 16:
`1 passed` (combined with focused suite: `8 passed`).

### Privacy scan

Focused assertions prove:

- answer/excerpt sentinels absent from DTO, terminalSnapshot, and stored event
  payloads after delete-driven redaction
- user question preserved on redacted turns
- composer source-kind and evidence-kind tokens expire at domain/source fence

## Residuals

- P8: system-wide privacy/audit sink scanning; DRIFT-29 audit/privacy breadth.
- P9: browser redaction UI / open Evidence panel close / reducer application of
  `turn.redacted`.
- P9-03: evidence/document location and content HTTP denial (routes not
  implemented; this slice does not invent them). Do not claim full M-11 closed.
- P11: deeper composer-ref assembly beyond delete-path token expiry.
- P12-03: deployed-ingress adversarial deletion review.
- DRIFT-29 remains IN_PROGRESS overall; only the chat-redaction/omission half
  is closed by P7-05.

This slice closes the server chat-projection half of M-11 and does not redefine
the closed Phase 1 chat capability manifest.
