# P8-01 Transactional Audit Allowlist Denial Privacy Evidence

Date: 2026-07-27

Slice: P8-01

Requirements and cases: FR-09; C-02; C-05; DRIFT-20; DRIFT-29 audit/privacy half

Status: DONE (focused unit proofs; disposable PostgreSQL denial/target_id assertions retained in foundation test when harness available)

## Implemented and retained behavior

- Inventory: `docs/_scratch/p8-01-audit-inventory.md` dispositions every closed
  event and production writer (`migrate`, `protected-helper`, exemption classes).
- Migrated onto `commit_protected_mutation`: source prep retry/cancel; source
  index retry terminal; source index cancel terminal (intermediate CANCELLING
  commit + remote delete remain outside the helper).
- Retained exemptions: upload `open-txn-object-put`; worker terminals; nested
  `chat.turn_redacted` flush; domain external-call-split finish/fail; orphan
  `source.deleted` / `user.disabled` / `user.enabled`.
- `require_admin` (KTD8): denial audit record/commit failure maps to
  `AuditError` / `503 audit_unavailable`; happy path remains `403` + durable
  `security.admin_route_denied` without resource `target_id`.
- Adversarial privacy scans over `audit_events` rows (conversation title
  sentinels; closed metadata keys).

## Verification

```bash
cd app
.venv/Scripts/python.exe -m pytest \
  tests/test_audit_call_site_matrix.py \
  tests/test_audit_denial_matrix.py \
  tests/test_audit_privacy_scan.py \
  tests/test_audit_service.py \
  tests/test_phase_one_observability_scope.py -q
```

Observed (2026-07-27):

```text
...............                                                          [100%]
15 passed
```

Optional PostgreSQL 16 (when disposable harness env is set):

```bash
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1 \
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/postgres \
.venv/Scripts/python.exe -m pytest \
  tests/test_postgres_audit.py \
  tests/test_postgres_foundation.py -q -k "audit or role_recheck"
```

## Residuals

- P8-02: safe JSON logs, request/trace correlation, bounded metrics.
- P8-03: liveness/readiness and cross-sink privacy/resilience gate.
- Phase 2: product audit-read/export.
- Orphan events remain reserved (no user disable/enable product API).
- P12: deployed-ingress adversarial breadth beyond focused audit-row proofs.
- Nested delete-fence outer-audit rollback on PostgreSQL remains covered by
  existing delete-redaction PG proofs when harness available; not re-run in
  this evidence capture.
- Broader AE6 privacy fixtures (credential rotate, upload filename, redaction
  excerpt plant → audit-row scan) and HTTP TestClient proof of member
  `/admin/*` → `503 audit_unavailable` on injected denial-audit failure remain
  follow-ups; unit denial-matrix + conversation title privacy scans landed.
