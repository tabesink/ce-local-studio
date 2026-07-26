# P6-02 Stateless Evidence Projection Evidence

Date: 2026-07-26

Owner: P6-02

Status: DONE

Requirements and cases: FR-05; M-02; M-03; C-01; C-02.

Tested code revision before this evidence-only closeout:
`c117fb133dc643b75348fe8c8f41e3adca41e884`.

## Implemented boundary

- `RetrievalEvidenceRequestDto` strips surrounding whitespace before applying
  its 1..2,000-character bound.
- The new closed `RetrievalEvidenceAnchorDto` exposes only a one-based page,
  optional bounded section label, and `section|page` fallback. It cannot carry
  a region or `region` fallback.
- The response model rejects result/Evidence contradictions. Stateless
  Evidence remains ID-free, ordered after final filtering/deduplication, and
  uses dense response-local citation labels.
- The existing P6-01 retrieval path still maps only current selected-domain
  canonical blocks and performs terminal domain/runtime/source reauthorization.
- The HTTP route validates the final public response and maps all known or
  unexpected internal retrieval categories to approved safe errors with
  request-ID correlation and private no-store caching.
- The endpoint creates no request-time database mutation. The P7 scaffold's
  separate durable turn Evidence seam remains operational and tested.

## Verification

### Focused service, HTTP, generated DTO, and chat-turn proof

```text
cd app
.\.venv\Scripts\python.exe -m pytest tests\test_scoped_retrieval.py tests\test_evidence_http_contract.py tests\test_authoritative_dto_components.py tests\test_generated_contract_gate.py tests\test_canonical_turn_event_behavior.py -q
```

Result: PASS, 50 tests.

The Evidence HTTP file was rerun after strengthening the endpoint privacy
assertions: PASS, 12 tests. The chat-turn characterization file passed 5 tests,
including durable source-document/source-block linkage and safe normalization
of a private retrieval failure.

### PostgreSQL 16 lifecycle and concurrency proof

Environment:

```text
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=postgresql+psycopg://context_engine:context_engine@127.0.0.1:5438/postgres
```

```text
cd app
.\.venv\Scripts\python.exe -m pytest tests\test_postgres_scoped_retrieval.py -q
```

Result: PASS, 5 tests against PostgreSQL 16.14. Barrier-driven transactions
prove stop/restart, reindex-ready, deletion, and preparation-replacement fences
plus simultaneous request isolation. The documented disposable database was
started from `app/compose.stack.yml` on loopback port 5438 before the successful
run; an earlier attempt made while that service was absent produced no test
result and is not counted as evidence.

### Retrieval/indexing regressions

```text
cd app
.\.venv\Scripts\python.exe -m pytest tests\test_lightrag_renderer_adapter.py tests\test_source_index_eligibility.py tests\test_postgres_source_index_eligibility.py -q
```

Result: PASS, 14 tests with the PostgreSQL opt-in variables set.

### Changed-boundary lint

```text
cd app
.\.venv\Scripts\python.exe -m ruff check context_engine\api\catalog_schemas.py context_engine\api\routes.py context_engine\services\evidence.py context_engine\services\chat_turns.py tests\test_scoped_retrieval.py tests\test_evidence_http_contract.py tests\test_postgres_scoped_retrieval.py tests\test_authoritative_dto_components.py tests\test_generated_contract_gate.py tests\test_canonical_turn_event_behavior.py
```

Result: PASS.

The complete backend package lint also passed:

```text
cd app
.\.venv\Scripts\python.exe -m ruff check context_engine
```

### Generated contracts

```text
$env:UV_CACHE_DIR='D:\Projects\ce-local-studio\.codex-uv-cache'
& 'C:\Program Files\Git\bin\bash.exe' scripts/check-generated-contracts.sh
```

Result: PASS. OpenAPI, public JSON Schema, SSE generation views, and generated
TypeScript clients regenerate without drift.

### Phase scope

```text
& 'C:\Program Files\Git\bin\bash.exe' scripts/check-doc-phase-scope.sh
```

Result: PASS, 65 governed files. The two Windows portability corrections in the
checker normalize CRLF input and backslash paths without changing the governed
scope rules.

### Broad backend regression

With the disposable PostgreSQL variables above:

```text
cd app
.\.venv\Scripts\python.exe -m pytest -q
```

Result: PASS, 194 tests on exact revision
`c117fb133dc643b75348fe8c8f41e3adca41e884`.

The applicable backend portion of `scripts/verify.sh` was run through the
existing locked virtual environment: package import, full package Ruff, the
complete backend suite, generated contracts, and phase scope all passed.
`uv lock --check` could not resolve from the intentionally isolated empty cache
without contacting PyPI; network escalation was denied. No dependency or
`app/uv.lock` change exists in this slice. Frontend and image/Compose build
checks are outside this backend-only P6 implementation boundary and remain in
their owning LFG shipping/browser and P10/P12 gates.

## Privacy and no-mutation evidence

- Response assertions reject private source/block fields, malformed anchors,
  contradictory result/Evidence pairs, unknown response fields, submitted
  question reflection, and dependency exception text.
- Captured application/HTTP logs are scanned for the submitted question,
  dependency exception, safe Evidence excerpt, and document label; none are
  logged. The safe excerpt and label appear only in the authorized success
  response.
- Service tests prove raw provider candidates never become excerpts and
  private question/health exceptions are absent from safe exception strings,
  cause/context chains, and formatted tracebacks.
- Every database table count is snapshotted after app startup and remains
  unchanged across the stateless request. The separate chat characterization
  confirms only the P7-owned turn path persists Evidence refs.
- The endpoint emits no audit event, trace payload, product metric, snapshot,
  export, or failure artifact, so those sinks are non-applicable to this
  endpoint-specific P6 proof. P8 owns the system-wide cross-sink scan and
  operational-safety closure.
- Fixtures contain only synthetic sentinels and canonical sample content; no
  provider payload or production identifier is stored.

## Rollout and recovery

- This slice has no database migration and creates no durable stateless
  Evidence. Rollback restores the prior DTO/route projection and regenerates
  contracts from that revision.
- Schema-v2 runtime reindex requirements and recovery remain documented by
  P6-01.
- Any future addition of a stateless Evidence ID, region anchor, new error
  code, source-content URL, or browser capability requires an approved contract
  change.

## Deferred ownership

- P7 owns durable Evidence IDs/refs, replay, redaction, grounded refusal, and
  orchestration.
- P8 owns system-wide audit/log/trace/metric privacy and resilience evidence.
- P9 owns Evidence inspector and governed document navigation.
- P10/P12 own deployed topology, recovery, and production release evidence.
