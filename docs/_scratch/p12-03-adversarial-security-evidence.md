# P12-03 Adversarial Security Review Evidence

Date: 2026-07-28

Slice: P12-03

Status: DONE (API / service / PostgreSQL-altitude gap-fill)

Plan: `docs/plans/2026-07-28-004-feat-p12-03-adversarial-security-review-plan.md`

Inventory: `docs/_scratch/p12-03-adversarial-security-inventory.md`

## What landed

| Item | Detail |
| --- | --- |
| Inventory | Four-lane credit / gap-fill / out-of-scope freeze |
| Gap suite | `app/tests/test_p12_03_adversarial_security.py` (G1–G6) |
| Credit citations | P1-03 authz, P8 privacy triad, P7-05 redact/omission, P6 mapping/fences |
| Product fixes | None required — existing fence/redact/mapping behavior satisfied gap tests |

## Gap tests added

| ID | Test | Cases |
| --- | --- | --- |
| G1 | `test_g1_document_content_unknown_and_deleting_share_document_not_found`, `test_g1_document_content_ineligible_matches_unknown_shape` | C-04 |
| G2 | `test_g2_cleanup_failure_then_retry_keeps_redaction_tokens_and_fence` | A-09 |
| G3 | `test_g3_composer_consume_after_delete_driven_expiry_is_unavailable` | M-09, A-09 |
| G4 | `test_g4_all_adversarial_hits_map_empty_then_grounded_refusal` | M-03 |
| G5 | `test_g5_post_domain_delete_new_domain_rag_fails_closed` | A-04, A-08, A-09 |
| G6 | `test_g6_enqueue_delete_public_projection_omits_answer_sentinel` | M-11, FR-09 |

## Commands

### Gap suite (default SQLite path)

```text
cd app
uv run --frozen --python 3.12 --extra test pytest tests/test_p12_03_adversarial_security.py -q
```

Observed: **7 passed**.

### Credit re-proof (representative)

```text
cd app
uv run --frozen --python 3.12 --extra test pytest \
  tests/test_audit_denial_matrix.py \
  tests/test_delete_redaction.py \
  tests/test_cross_sink_privacy_scan.py \
  tests/test_scoped_retrieval.py::test_exact_schema_v2_mapping_uses_one_query_canonical_content_and_dense_first_wins \
  tests/test_chat_orchestration.py::test_m03_ae2_empty_corpus_completes_no_grounded_context \
  -q
```

### Opted-in PostgreSQL 16 (credit barriers; not required to re-run for gap suite)

```text
CONTEXT_ENGINE_ALLOW_DISPOSABLE_DATABASE_TESTS=1 \
CONTEXT_ENGINE_TEST_POSTGRES_ADMIN_URL=<admin-url> \
uv run --frozen --python 3.12 --extra test pytest -m postgresql \
  tests/test_postgres_foundation.py::test_p1_03_role_recheck_denial_audit_and_owner_isolation_on_postgresql_16 \
  tests/test_postgres_delete_redaction_barriers.py \
  tests/test_postgres_scoped_retrieval.py \
  -q
```

## Case ID matrix

| Case | Evidence |
| --- | --- |
| M-03 | G4 + credit empty-corpus / mapping discard |
| M-08 | Credit P1-03 |
| M-09 | G3 |
| M-11 | G6 + credit P7-05 (server half only) |
| A-01 | Credit P8 credential plants |
| A-04 | G5 |
| A-08 | G5 + credit eligibility suite |
| A-09 | G2, G3, G5 + credit P7-05 |
| A-10 | Credit domain enqueue redact |
| C-01 | Credit PG scoped retrieval concurrent isolation |
| C-02 | Credit audit denial matrix |
| C-04 | G1 + credit P1-03 / chat cross-owner |
| C-05 | Credit P1-03 role recheck |

## Residuals

| Residual | Owner |
| --- | --- |
| Deployed-ingress TLS / Host/Origin / direct-API denial / stream-drain | P12-05 |
| Playwright / browser storage / BFCache / two-user cache / M-11 open-panel | P12-07 |
| Backup/restore of redactions + audit continuity | P12-04 |
| SBOM / provenance | P12-06 |
| Production acceptance aggregation | P12-08 |
| P11-04 Evidence attach UX | product DEFER |

## Tracker updates

- `docs/master-build-plan.md` P12-03 → DONE with this evidence link
- P7-05 closure residual rewritten: API adversarial security → P12-03; deployed-ingress adversarial deletion → P12-05
- DRIFT-29 note: API adversarial re-proof credited; browser M-11 half remains open

## Explicit non-claims

This slice does **not** claim ingress TLS/direct-API denial, Playwright acceptance, full DRIFT-29/M-11 browser closure, backup drills, or B0 complete.
