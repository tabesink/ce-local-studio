# P6-01 Scoped Retrieval and Provenance Evidence

Date: 2026-07-25

Owner: P6-01

Status: DONE

Requirements and cases: FR-05; A-08; C-01; C-02; DRIFT-27; DRIFT-34.

Tested branch revision before this evidence-only closeout: `f03e15f`.

## Implemented boundary

- Index lifecycle and scoped retrieval now use separate private protocols.
- Retrieval admits one server-selected domain through bounded process-level
  global/per-domain gates. One deadline covers admission, native lock wait,
  provider execution, late-result rejection, and bounded cleanup.
- The service and adapters enforce a maximum of 10 candidates plus positive
  individual and aggregate UTF-8 byte limits. Malformed results, saturation,
  timeout, and unavailability become content-free typed failures.
- The private LightRAG handoff is schema v2. `CE_SOURCE` remains the
  document-level header, while every `CE_BLOCK` first line is self-contained
  with schema, source ID, source SHA-256, block ID, and source order.
- Mapping accepts only that anchored first line, rejects additional reserved
  provenance tokens, uses current canonical block content rather than provider
  text, preserves surviving adapter order, deduplicates first occurrence, and
  assigns dense ranks.
- Before provider work, the service freezes domain control/runtime identity and
  eligible-source preparation/index generation, request ID, index content hash,
  and source SHA-256. One joined post-call SQL statement compares all frozen
  predicates and the active-operation fence in one PostgreSQL snapshot.
- Both the existing Evidence route and the P7 chat scaffold delegate through
  this P6 boundary. Their public DTO/error/SSE behavior is unchanged and remains
  owned by P6-02/P7.

## Verification

### Focused unit, adapter, PostgreSQL, eligibility, and chat regression

Environment:

```text
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=postgresql+psycopg://context_engine:context_engine@127.0.0.1:5438/postgres
```

Command:

```text
cd app
.\.venv\Scripts\python.exe -m pytest tests/test_scoped_retrieval.py tests/test_lightrag_renderer_adapter.py tests/test_postgres_scoped_retrieval.py tests/test_postgres_source_index_eligibility.py tests/test_source_index_eligibility.py tests/test_canonical_turn_event_behavior.py tests/test_chat_sse_http_contract.py -q
```

Result: PASS, 31 tests. The PostgreSQL 16 matrix uses two transaction
sessions, a retrieval thread, and barriers rather than sleeps. It proves that
stop/restart, reindex/new-ready, deletion fencing, and preparation replacement
committed before provider return cannot map the stale candidate.

### Focused lint

```text
cd app
.\.venv\Scripts\python.exe -m ruff check context_engine\services\evidence.py context_engine\services\indexing.py context_engine\services\chat_turns.py context_engine\config.py tests\test_scoped_retrieval.py tests\test_postgres_scoped_retrieval.py
```

Result: PASS.

### Generated-contract stability

`scripts/check-generated-contracts.sh` could not start through the Windows WSL
shim because no WSL distribution is installed. The equivalent pinned Windows
gate regenerated OpenAPI, public DTO schema, SSE schema/generation view, and
both TypeScript clients into a temporary directory, then compared normalized
content against the committed artifacts.

Result: PASS; no HTTP, DTO, SSE, or generated-client drift.

### Phase-scope gate

Git Bash on this Windows checkout needed an isolated LF-normalized archive and
a forward-slash `rg --files` test wrapper because the native Windows `rg`
returns backslash paths. The canonical `scripts/check-doc-phase-scope.sh` logic
then ran unchanged against that archive.

Result: PASS, 64 governed files.

## Privacy and failure evidence

- Sentinel questions and oversized raw candidates are asserted absent from
  normalized exceptions.
- Provider candidate text is never used as the Evidence excerpt; mapping copies
  only current canonical block content into the still-partial P6-02-owned
  projection.
- Raw candidates and private source/block/index identities are call-scoped and
  are not persisted, logged, traced, audited, or returned by a new public
  contract.
- Synthetic private adapter fixtures use invented IDs/questions only. No
  captured provider payload is stored.

## Rollout and recovery

- Schema-v2 rendering changes index content hashes and therefore request
  identities. Existing schema-v1 ready runtime content must be requeued and
  reindexed before it can produce accepted P6 candidates.
- Schema-v1 or transformed candidates fail closed as no mapped context. There
  is no fuzzy or legacy marker fallback.
- The database schema is unchanged. Rollback restores the prior service code;
  schema-v2 runtime derivatives remain rebuildable and may be deleted/reindexed
  idempotently through the existing P5 lifecycle.

## Deferred ownership

- P6-02: closed authorized Evidence DTOs, safe labels/excerpts/opaque refs,
  deterministic citation order, anchors, member route failures, and document
  navigation.
- P7: intent classification, repair/orchestration, durable turn persistence,
  grounded refusal, and canonical SSE execution.
- P8: broad cross-sink privacy and operational-safety scans.
- P9: Evidence inspector and governed document UX.
- P10/P12: deployed multi-replica capacity and production evidence beyond this
  process-local adapter protection.
