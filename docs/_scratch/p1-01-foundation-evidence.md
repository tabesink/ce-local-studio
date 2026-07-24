# P1-01 PostgreSQL Foundation Evidence

Date: 2026-07-24

Slice: P1-01

Requirement: FR-11 foundation boundary

Status: DONE

## Implemented and retained surfaces

- Retained `context_engine.app:create_app` as the canonical FastAPI factory.
- Retained `Settings` as database configuration ownership.
- Retained `create_db_engine`, `create_session_factory`, and the explicit
  Alembic release boundary.
- Added an opt-in PostgreSQL-only proof in
  `app/tests/test_postgres_foundation.py` and registered its pytest marker.
- No production application code or migration was changed by this slice.

## Authoritative verification

```bash
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1 \
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=postgresql+psycopg://.../postgres \
.venv/bin/python -m pytest tests/test_postgres_foundation.py -q
```

Observed against an ephemeral `postgres:16` container:

```text
..                                                                       [100%]
2 passed
```

The proof asserts `server_version_num` is PostgreSQL major version 16 before
creating test databases.

## Scenario evidence

### Fresh install

1. Created a uniquely named empty disposable database.
2. Confirmed the database had no application tables.
3. Constructed the canonical FastAPI app and confirmed construction did not
   create schema or invoke migrations.
4. Ran Alembic from no schema to the single head `d07141ac7d95`.
5. Confirmed the database revision equals the checked-in single head.
6. Exercised canonical settings, engine, and session-factory behavior through a
   real PostgreSQL query and commit.
7. Ran `alembic check` successfully against canonical ORM metadata.

### Supported in-rebuild upgrade

1. Upgraded an empty disposable database to baseline `724564649a13`.
2. Inserted one synthetic user row with no real credential material.
3. Upgraded through `014b33300438` to head `d07141ac7d95`.
4. Confirmed the row remained and the canonical turn-event table existed.
5. Downgraded the two incremental revisions to `724564649a13` and confirmed the
   synthetic user remained while the incremental event table was removed.
6. Re-upgraded to head and ran `alembic check` successfully.

## Safety and privacy decisions

- The test skips unless disposable-database testing is explicitly enabled and
  an administrative PostgreSQL URL is supplied.
- It fails closed for a non-PostgreSQL URL or a server outside major version 16.
- It creates and drops only internally generated names matching the
  `ce_p101_*_<uuid>` pattern.
- Teardown runs in `finally`, terminates only connections to the generated
  database, and does not alter the administrative database.
- Fixtures contain only synthetic identifiers and a deliberately invalid
  password-hash label.

## Rollback and restore boundary

The two post-baseline revisions are mechanically reversible to
`724564649a13`; real PostgreSQL proof demonstrates retained baseline data and
successful re-upgrade. Downgrading the baseline itself drops the Phase 1 schema
and is not an in-place production rollback strategy.

Production response to a failed release migration is to stop dependent
replicas, preserve the database, restore from the environment's verified
backup when data-destructive recovery is required, or ship a reviewed forward
fix. Do not run `downgrade base` against populated production state. Migration
from an unknown populated legacy database, including deferred publication
contraction, remains explicitly blocked under P12-01 and
`docs/architecture/legacy-persistence-retirement.md`.

## Characterization note

The first fresh-install run reached the application factory but the test setup
omitted `testing=True`; expected fail-closed encryption-key validation stopped
construction. The fixture was corrected to use the existing test-mode key
path, after which both PostgreSQL scenarios passed. This was a test setup
defect, not a production behavior change.
