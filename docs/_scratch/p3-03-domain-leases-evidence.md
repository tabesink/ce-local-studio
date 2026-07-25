# P3-03 Domain Lease / Generation / Delete Worker Evidence

Date: 2026-07-25

Slice: P3-03

Requirements and cases: FR-03; A-03; A-04 fence; A-05; A-10; DRIFT-12 race
half; DRIFT-32 domain half

Status: DONE

## Implemented and retained behavior

- Start/stop keep sync-in-request completion but assign short-lived lifecycle
  leases and apply state only through `update_domain_state_if_current` (generation
  + runtime instance fence). Stale completion cancels the op and leaves domain
  state unchanged.
- Stop/delete intent continues to make `domain_available` false immediately via
  active-operation / `deleting` fences (A-04 / A-10 member selection).
- Delete supersedes active start/stop by cancelling the active op, bumping
  generation, and queueing delete (A-05).
- `DomainDeleteWorker` heartbeats the lease (&lt; ⅓ lease cadence via renew-on-step),
  rejects completion when lease/owner is lost, cancels on generation drift, and
  reclaims expired running deletes (including uncertain ones).
- `reconcile_uncertain_lifecycle_operations` probes uncertain start/stop ops and
  terminalizes when controller health is clear; delete uncertain remains
  lease-reclaim driven.

## Verification

```bash
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1 \
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=postgresql+psycopg://context_engine:context_engine@127.0.0.1:5438/postgres \
app/.venv/Scripts/python.exe -m pytest \
  tests/test_postgres_domain_leases.py \
  tests/test_postgres_domains.py \
  tests/test_domain_runtime_controller.py \
  tests/test_domains_service.py -q
```

Observed:

```text
...........                                                              [100%]
11 passed
```

PostgreSQL assertions include stale-generation start no-op, uncertain stop fence +
reconcile, delete supersede of active stop, delete worker happy path, expired
lease reclaim, and stale delete completion cancel.

## Residuals / deferred

- Mid-turn chat A-04 `domain_became_unavailable` policy remains P7.
- Full async start/stop workers remain unnecessary after fence proofs.
- Index-side DRIFT-32 reconciliation remains P5-03.
- Optional live Docker daemon suite remains non-gating.
