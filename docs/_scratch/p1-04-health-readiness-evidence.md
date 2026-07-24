# P1-04 Health, Error, and Logging Evidence

Date: 2026-07-24

Slice: P1-04

Requirements: FR-09, FR-11, A-13

Status: DONE

## Implemented and retained behavior

- Retained P0-03 server-owned request IDs and closed safe error envelopes.
- Added internal readiness aggregation for database connectivity, exact Alembic
  head `d07141ac7d95`, and existence of an enabled administrator.
- Kept liveness process-only and independent from readiness dependencies.
- Added private no-store headers to the canonical JSON error constructor.
- Changed unclassified structured log records to a bounded `unclassified`
  event instead of falling back to a raw message.
- Retained explicit allowlisted `safe_log` events and correlation dimensions.
- Did not add an object-store implementation or pretend a development path is
  production readiness evidence.

## Proof-first evidence

The PostgreSQL readiness characterization first showed a migrated database with
no administrator incorrectly returned `200`. After adding the aggregate, the
test advanced to a missing no-store header on safe `503` errors; the canonical
error constructor was corrected. Focused health regression then showed the new
service caught only SQLAlchemy exceptions and old test doubles modeled only
`SELECT 1`. Exception mapping was broadened to all ordinary exceptions and the
doubles were updated for schema/bootstrap checks.

The logging privacy test showed unclassified records copied raw messages into
the JSON `event`; replacing that fallback with `unclassified` closed the leak.

## Verification

Focused logging, health, error, and request-ID checks:

```text
.venv/bin/python -m pytest \
  tests/test_structured_logging.py tests/test_health_contract.py \
  tests/test_api_errors.py tests/test_api_conventions.py -q
............                                                             [100%]
12 passed
```

Real PostgreSQL 16 foundation/auth/authorization/readiness:

```text
.venv/bin/python -m pytest tests/test_postgres_foundation.py -q
.........                                                                [100%]
9 passed
```

Identity and generated-contract regression:

```text
..........................                                               [100%]
26 passed
```

The only warning is the dependency-owned Starlette `TestClient` HTTPX
compatibility deprecation.

## Readiness assertions

- Empty-bootstrap state returns safe correlated `503` while liveness stays
  `200`.
- Explicit administrator bootstrap moves readiness to `200`.
- Behind/mismatched Alembic version returns the same safe `503` and never runs a
  migration from the API.
- Disabling the only administrator returns the same safe `503`.
- Private readiness reason strings never cross the HTTP boundary.
- Provider and domain/runtime state are not global readiness dependencies.

## Logging and error privacy assertions

- Canonical errors include request ID, closed code/message/fields, and
  `Cache-Control: private, no-store, no-transform`.
- `safe_log` drops password, username, body, and exception keyword fields.
- Unclassified logger messages cannot become event values or leak their raw
  text through the JSON formatter.
- Request logs retain bounded method, route template, status, outcome, elapsed
  time, actor kind, and safe correlation fields.

## Deferred boundaries

P4 must provide the governed object-storage capability contract before it can
be probed. P10-02 composes that indispensable capability into final deployment
readiness and proves worker readiness. P9-05 owns identity-partitioned BFF and
browser cache behavior. P8 owns broader privacy scans across all operational
sinks.
