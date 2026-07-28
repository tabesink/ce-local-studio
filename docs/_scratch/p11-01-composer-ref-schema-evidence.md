# P11-01 Composer Ref Schema & Seeds Evidence

Date: 2026-07-27  
Status: DONE (with explicit residuals)  
Plan: `docs/plans/2026-07-27-016-feat-p11-01-composer-ref-schema-seeds-plan.md`  
Branch: `feat/p11-01-composer-ref-schema-seeds`  
Inventory: `docs/_scratch/p11-01-composer-ref-schema-inventory.md`

## What landed

| Item | Result |
| --- | --- |
| Schema inventory | `docs/_scratch/p11-01-composer-ref-schema-inventory.md` — retain brownfield tables; no additive DDL |
| Closed kind / hash / public_ref proofs | `app/tests/test_phase_one_schema_scope.py` (`test_phase_one_composer_ref_tables_match_schema_contract`) |
| Opt-in PostgreSQL 16 constraint suite | `app/tests/test_postgres_composer_ref_schema.py` (requires `CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1`) |
| Gated prompt-template fixtures | `app/context_engine/dev/seed_prompt_templates.py` — `template_safety_summary` / `template_disabled` |
| Gated token + accepted-ref fixtures | `app/context_engine/dev/seed_composer_refs.py` — parents, 8 hash-only tokens, 4 accepted refs |
| Dual seed gate | `app/context_engine/dev/seed_gate.py` — `CE_ENVIRONMENT=development\|test` ∧ `CE_ALLOW_TEST_SEED=true` |
| Token expiry clock | `seed_composer_ref_fixtures(now=...)` defaults to `utc_now()` so valid fixtures stay usable; tests freeze `SEED_CLOCK` |
| Destructive reset | `--reset` / `reset=True` allowed only when `CE_ENVIRONMENT=test` |
| CLI seed entry | `app/context_engine/dev/seed.py` → `seed_composer_ref_fixtures` |
| Lifespan non-install | Demo template upsert removed from API lifespan / service catalog |
| Seed contract doc | `docs/quality/seeded-demo-and-test-data.md` Composer section |
| Unit tests | `test_composer_seed_templates.py`, `test_composer_seed_refs.py` |

## Fixture coverage (P11-01 durable world)

Templates: `template_safety_summary`, `template_disabled`.

Token fixture keys (hashes only; raw plaintext absent from seed modules):  
`token_mina_source_valid`, `token_mina_evidence_valid`, `token_mina_template_valid`,  
`token_mina_expired`, `token_noah_wrong_owner`, `token_mina_wrong_domain`,  
`token_mina_deleted_target`, `token_mina_disabled_template`.

Accepted-ref public refs:  
`accepted_mina_source_01`, `accepted_mina_evidence_01`, `accepted_mina_template_01`,  
`accepted_mina_redacted_01` (labels cleared).

Reserved unseeded key for P11-02 / DRIFT-26: `token_mina_consumed_source`.

## Commands and results

```text
cd app
python -m pytest tests/test_phase_one_schema_scope.py -q -k composer_ref
# PASS (composer-ref schema contract assertion)

python -m pytest tests/test_composer_seed_templates.py tests/test_composer_seed_refs.py -q
# ........ [100%] PASS
```

PostgreSQL constraint suite remains opt-in:

```text
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1 \
  python -m pytest tests/test_postgres_composer_ref_schema.py -q
```

## Operator / Compose note (gated seed)

Composer fixtures are not installed by API lifespan. Local/demo DBs that need the durable composer world must run the gated seed entry under both allowlist env vars, for example:

```text
CE_ENVIRONMENT=development CE_ALLOW_TEST_SEED=true \
  python -m context_engine.dev.seed
```

Compose product services must not set `CE_ALLOW_TEST_SEED=true` for production-like matrices. Seed writes fail closed without the dual gate.

## Privacy guarantees evidenced

- Token rows persist 64-char hashes only; no raw token column or seed plaintext.
- Accepted-ref public projection helper exposes only `id` / `kind` / `order` / `label` / `description`.
- Template bodies remain private; public surfaces use safe labels only.
- Redacted accepted-ref fixture nulls safe label/description.

## Residuals (honest non-claims)

| Residual | Owner |
| --- | --- |
| One-use consume column + `token_mina_consumed_source` durable row | P11-02 / DRIFT-26 |
| Discover HTTP, minting, ownership/expiry/domain/target validation | P11-02 |
| `token` vs `refToken` catalog/runtime drift; max-ref parity | P11-02 |
| Private assembly, fingerprint consistency, replay/conflict | P11-03 |
| Browser E2E discover/consume flows | P11-02+ / later gates |
| Invented FKs on accepted-ref private link columns | out of schema contract |

## Tracker updates

- `docs/master-build-plan.md` P11-01 → DONE; evidence pointer set.
- Brownfield register: schema/seed foundation progress noted; hashed-token consumption row and DRIFT-26 remain NOT_STARTED.
