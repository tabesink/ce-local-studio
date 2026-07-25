# P3-02 Runtime Controller Port Evidence

Date: 2026-07-25

Slice: P3-02

Requirements and cases: FR-03; domain runtime controller port contract
(stable operation key, bounded timeout, typed uncertain outcome)

Status: DONE

## Implemented and retained behavior

- Controllers live in `app/context_engine/adapters/domain_runtime_controller.py`
  with Local/Docker implementations and `controller_from_settings`.
- Mutating calls require `operation_key` and `control_generation`; Docker
  payloads and local runtime records carry both.
- Typed `RuntimeControllerResult` outcomes: `succeeded` / `failed` /
  `uncertain`. Docker `TimeoutExpired` maps to `uncertain`.
- Domain lifecycle service maps uncertain outcomes to a non-terminal operation
  message (still `running`/`queued`) and `503 dependency_unavailable` on the
  sync pilot path; reconciliation loops remain P3-03.
- `tools/domain_runtime_controller.py` remains the private Docker CLI backend
  and accepts the extended payload fields without schema breakage.

## Verification

```bash
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1 \
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=postgresql+psycopg://context_engine:context_engine@127.0.0.1:5438/postgres \
app/.venv/Scripts/python.exe -m pytest \
  tests/test_domain_runtime_controller.py \
  tests/test_domains_service.py \
  tests/test_postgres_domains.py -q
```

Observed:

```text
..........                                                               [100%]
10 passed
```

## Residuals / deferred

- Lease/heartbeat and DRIFT-32 reconciliation worker loops (P3-03).
- Optional `@pytest.mark.integration_docker` live daemon suite (not a P3-02 gate).
- Moving start/stop fully onto leased workers (P3-03).
