# P11-02 Composer Ref Discover / Validate / Consume Evidence

Date: 2026-07-27  
Status: DONE (with explicit residuals)  
Plan: `docs/plans/2026-07-27-017-feat-p11-02-composer-ref-discover-consume-plan.md`  
Branch: `feat/p11-02-composer-ref-discover-consume`

## What landed

| Item | Result |
| --- | --- |
| Consume column | `composer_ref_tokens.consumed_at` nullable timestamp in schema, model, Alembic `f1a8c3d04e92` |
| Already-consumed seed | `token_mina_consumed_source` durable under dual seed gate |
| Discover DTO | `token` + `expiresAt` via `ComposerRefDto` response model; no `refToken` |
| Max refs | `MAX_COMPOSER_REFS` / discover `MAX_DISCOVERY_LIMIT` = 25; OpenAPI regenerated |
| Error allowlist | Discover `_composer_ref_api_error` fail-closed; unavailable → `operation_conflict` |
| Validate unconsumed | `_token_row_by_hash` rejects `consumed_at is not None` |
| Atomic consume | `consume_composer_ref_tokens` with `FOR UPDATE`; called only after post-lock replay fence on new-turn insert |
| Contracts | `openapi.json`, `public-dtos.schema.json`, generated `openapi.ts` refreshed |
| Chat-shell type | Hand `refToken` type replaced with generated `ComposerRefDto` (UI still unused) |

## Commands and results

```text
cd app
python -m pytest tests/test_phase_one_schema_scope.py -q -k composer_ref
# PASS

python -m pytest tests/test_composer_seed_refs.py tests/test_composer_refs_discover_http_contract.py tests/test_composer_refs_consume.py tests/test_composer_refs_phase_one.py -q
# PASS (includes turn-start consume/reuse/replay + turns:stream operation_conflict remap)
```

Opt-in PostgreSQL schema/race suites require:

```text
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1 \
  CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=... \
  python -m pytest tests/test_postgres_composer_ref_schema.py tests/test_postgres_composer_ref_consume_race.py -q
```

## Privacy guarantees evidenced

- Discover returns raw tokens only in the HTTP response; DB stores 64-char hashes.
- Seed modules persist hashes / fixture keys only; no committed raw token plaintext.
- Public discover/turn errors use closed ErrorCodes; internal `composer_ref_unavailable` does not escape discover.
- Denial messages do not expose private target IDs.

## Residuals (honest non-claims)

| Residual | Owner |
| --- | --- |
| Private context assembly / fingerprint consistency | P11-03 |
| Replay-without-token / deeper idempotency conflict matrix | P11-03 / DRIFT-26 remainder |
| Opt-in PG AE5 race suite file exists (`test_postgres_composer_ref_consume_race.py`); live green run depends on disposable PG env | operator matrix |
| Browser References discover UI unlock / E2E | later gates |
| Per-kind cap catalog amendment (brownfield 4 retained) | contract change if desired |

## Tracker updates

- `docs/master-build-plan.md` P11-02 → DONE; evidence pointer set.
- Brownfield register: DRIFT-26 consume/bind denial advanced; replay-without-token remains P11-03; hashed-token foundation row notes P11-02 consume.
