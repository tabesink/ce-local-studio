# P1-01 Foundation Brownfield Inventory

Date: 2026-07-24

Owner: P1-01

Status: DONE

## Scope

This inventory is the required brownfield checkpoint for the P1-01 FastAPI,
settings, PostgreSQL engine/session, and Alembic foundation slice. Existing
files are evidence only. P1-01 receives completion credit only after the
retained foundation passes its task-owned PostgreSQL 16 boundary proof.

P1-01 does not claim the identity/session behavior owned by P1-02 and P1-05,
readiness behavior owned by P1-04, append-only audit behavior owned by P1-06,
or the populated legacy compatibility decision and proof owned by P12-01.

## Disposition register

| Surface | Current evidence | Disposition | P1-01 action and completion proof |
| --- | --- | --- | --- |
| FastAPI application factory | `context_engine.app:create_app` owns application construction and lifespan wiring | retain-and-reverify | Prove the factory can construct against the migrated PostgreSQL settings without running migrations from replica startup |
| Settings and database URL | `context_engine.config.Settings` supplies the SQLAlchemy URL and the development launcher exports an explicit PostgreSQL URL | retain-and-reverify | Exercise a PostgreSQL URL through the canonical settings-to-engine path; keep environment-specific values outside source |
| SQLAlchemy engine | `context_engine.db.create_db_engine` uses SQLAlchemy 2, `pool_pre_ping`, and a bounded SQLite compatibility branch | retain-and-reverify | Prove the production branch selects PostgreSQL and connects to PostgreSQL 16; SQLite remains test convenience only |
| Session factory and scope | `create_session_factory` disables autocommit/autoflush, preserves loaded values after commit, and `session_scope` closes sessions | retain-and-reverify | Prove commit/query/close behavior through the canonical factory against the disposable PostgreSQL database |
| Alembic environment | `app/migrations/env.py` imports canonical ORM metadata, accepts `CONTEXT_ENGINE_DATABASE_URL`, compares types, and uses `NullPool` | retain-and-reverify | Prove one linear head, fresh install to head, exact current head, and no metadata drift on PostgreSQL 16 |
| Migration chain | Baseline `724564649a13` advances through `014b33300438` to `d07141ac7d95` | retain-and-reverify | Run clean upgrade and baseline-to-head upgrade with a representative retained row; keep populated pre-rebuild retirement under P12-01 |
| Release migration boundary | Compose has a one-shot `migrate` service and API/worker depend on its successful completion; `scripts/dev.sh` migrates before starting replicas | retain-and-reverify | Preserve explicit release migration ownership and prove application construction does not call Alembic |
| PostgreSQL verification harness | Existing focused tests use SQLite and therefore cannot prove PostgreSQL version, dialect behavior, migration SQL, or session behavior | add | Add a disposable-database PostgreSQL 16 proof that fails closed for a non-test target and always cleans up its temporary database |
| Migration recovery notes | Downgrade functions exist, but the supported rollback/restore boundary is not recorded for this slice | add | Record forward-fix/default rollback guidance and the safe disposable-database downgrade evidence; destructive populated contraction remains prohibited |

## Retained invariants

- PostgreSQL 16 and Alembic are the production persistence authority.
- Application replicas never run migrations on startup.
- One canonical `Base.metadata` drives schema comparison.
- The migration chain has one head and no branch ambiguity.
- External calls and later feature state transitions remain outside P1-01.
- SQLite-specific handling remains isolated and cannot count as deployment,
  migration, locking, or concurrency evidence.

## Gaps closed by task-owned evidence

1. A task-owned proof creates a disposable PostgreSQL 16 database and
   upgrades it from empty state to Alembic head.
2. PostgreSQL proof upgrades the checked-in baseline to head while retaining
   representative synthetic data.
3. `alembic check` compares migrated PostgreSQL state with canonical ORM
   metadata on both proof paths.
4. The canonical session factory has real PostgreSQL query/commit evidence.
5. Rollback/restore behavior is recorded in
   `docs/_scratch/p1-01-foundation-evidence.md`.

## Completed evidence design

The P1-01 proof will use an explicitly configured administrative PostgreSQL
test URL to create a uniquely named disposable database. It will reject a
non-PostgreSQL server, reject PostgreSQL versions other than 16, reject unsafe
database targets, run Alembic through the canonical environment, exercise the
SQLAlchemy session factory, verify the linear head and metadata drift check,
and drop the disposable database in a `finally` path.

The proof will cover both:

- a fresh install from no schema to `d07141ac7d95`; and
- the supported in-rebuild upgrade from `724564649a13` to head with a retained
  synthetic user row.

It does not authorize or simulate migration from an unknown populated legacy
database. That remains blocked under P12-01 and
`docs/architecture/legacy-persistence-retirement.md`.
