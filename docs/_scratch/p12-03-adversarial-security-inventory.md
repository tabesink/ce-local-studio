# P12-03 Adversarial Security Inventory

Date: 2026-07-28

Owner: P12-03

Status: DONE — inventory freeze before gap-fill tests

Plan: `docs/plans/2026-07-28-004-feat-p12-03-adversarial-security-review-plan.md`

Altitude: FastAPI / service gap-fill (default SQLite) plus cited prior PostgreSQL credit barriers.
Deployed-ingress TLS/direct-API → P12-05.
Browser storage / BFCache / two-user cache / Playwright → P12-07.
Backup/restore → P12-04. P11-04 Evidence attach → product DEFER.

## Disposition legend

| Disposition | Meaning |
| --- | --- |
| credit | Existing real-boundary proof cited; no new test required |
| gap-fill | Add adversarial test in this slice |
| out-of-scope | Owned by named peer residual |

---

## Lane A — Authorization

| Surface | Existing proof | Disposition | Cases |
| --- | --- | --- | --- |
| Member → admin route denial + audit | `test_audit_denial_matrix.py` | credit | C-05, C-02 |
| Role recheck / disablement / admin≠owner conversation GET | `test_postgres_foundation.py::test_p1_03_role_recheck_denial_audit_and_owner_isolation_on_postgresql_16` | credit | C-04, C-05, M-08 |
| Cross-owner conversation/turn start | `test_chat_turn_route_http_contract.py` (`test_m07_ae8_*`) | credit | C-04 |
| Cross-owner SSE cancel | `test_chat_sse_http_contract.py` (`test_c01_cancel_cross_owner_*`) | credit | C-04 |
| Evidence location wrong owner → 404 | `test_documents_http_contract.py::test_evidence_location_http_wrong_owner_is_404_without_service_mock` | credit | C-04 |
| Document content HTTP unknown / wrong-eligibility same shape | mocked content only in HTTP suite; service has eligibility fences | gap-fill | C-04 |
| Ownership-404 audit events | Explicitly absent (P8-01) | credit (absence) | — |
| Host/Origin/CSRF through public ingress | — | out-of-scope | P12-05 |
| Two-user browser cache isolation | — | out-of-scope | P12-07 |

## Lane B — Secret / content leakage

| Surface | Existing proof | Disposition | Cases |
| --- | --- | --- | --- |
| Audit sink privacy | `test_audit_privacy_scan.py` | credit | FR-09 |
| Log + metric sink privacy | `test_log_metric_privacy_scan.py` | credit | FR-09 |
| Cross-sink + health privacy | `test_cross_sink_privacy_scan.py` | credit | FR-09 |
| Public turn/evidence projection privacy | `test_chat_orchestration.py::test_m03_ae6_*` | credit | M-03 |
| Redacted DTO/SSE omission | `test_delete_redaction.py` source-delete omission | credit | M-11 |
| Privacy plant via full `enqueue_delete_*` then sinks | Cross-sink uses helper redact, not full enqueue | gap-fill (extend plant) | M-11, FR-09 |
| Composer/assembly tokens in sinks | Partial via credential/upload plants | credit + cite; deepen only if plant shows hole | M-09, A-01 |
| Browser storage / BFCache leak scan | — | out-of-scope | P12-07 |

## Lane C — Deletion / redaction / fence recovery

| Surface | Existing proof | Disposition | Cases |
| --- | --- | --- | --- |
| Source/domain enqueue redact + token expiry | `test_delete_redaction.py`, `test_postgres_delete_redaction_barriers.py` | credit | A-09, A-10, M-11 |
| Late complete cannot un-redact | `test_delete_redaction.py::test_late_complete_*`, PG barriers | credit | A-09, R13 |
| Cleanup fail → retry stickiness (answer/tokens/eligibility) | Happy-path workers only | gap-fill | A-09 |
| Composer consume / turn-start after delete-driven expiry | Validate-after-delete credited; consume/start path thin | gap-fill | M-09, A-09 |
| Post-delete evidence location fence | `test_documents_service.py::test_get_evidence_location_delete_and_redaction_fences` | credit | M-11 |
| Open Evidence panel / browser cache after delete | — | out-of-scope | P12-07 / M-11 browser |
| Deployed-ingress adversarial deletion | — | out-of-scope | P12-05 |

## Lane D — Adversarial retrieval

| Surface | Existing proof | Disposition | Cases |
| --- | --- | --- | --- |
| Mapping discard unmapped/wrong-hash/order | `test_scoped_retrieval.py::test_exact_schema_v2_mapping_*` | credit | M-03 |
| Wrong-domain / v1 fail closed (PG) | `test_postgres_scoped_retrieval.py` | credit | M-03, C-01 |
| Mid-retrieval delete fence | `test_postgres_scoped_retrieval.py` fence=`delete` | credit | A-09 |
| Empty corpus → `no_grounded_context`, `grounded_calls==0` | `test_chat_orchestration.py::test_m03_ae2_*` | credit | M-03 |
| Adapter returns ONLY unmapped/wrong-domain hits → grounded refusal | Split credit; no single orchestration path | gap-fill | M-03 |
| Post-`enqueue_delete` new `domain_rag` / retrieve fail closed | Mid-retrieval + stopped-domain only | gap-fill | A-04, A-08, A-09 |
| Source eligibility predicates | `test_source_index_eligibility.py` | credit | A-08 |
| Capacity / concurrent-stream 429 at ingress | — | out-of-scope | P12-07 / P12-05 |

---

## Gap-fill worklist (this slice)

| ID | Gap | Primary extend target |
| --- | --- | --- |
| G1 | Document content HTTP unknown/ineligible → same `document_not_found` family as unknown | `app/tests/test_documents_http_contract.py` / `test_documents_service.py` |
| G2 | Cleanup fail → retry; redaction + tokens + eligibility stick | `app/tests/test_postgres_delete_redaction_barriers.py` |
| G3 | Composer consume / turn-start after delete-driven token expiry | `app/tests/test_composer_refs_consume.py` or `test_delete_redaction.py` |
| G4 | Only unmapped/wrong-domain hits → orchestration grounded refusal | `app/tests/test_chat_orchestration.py` |
| G5 | Post-`enqueue_delete` new domain_rag / retrieve fail closed | `app/tests/test_delete_redaction.py` + chat turn / scoped retrieval helpers |
| G6 | Cross-sink plant includes full `enqueue_delete_source` path | `app/tests/test_cross_sink_privacy_scan.py` (+ DTO omission in `test_p12_03_adversarial_security.py`) |

## Explicit non-claims

- No TLS / Host / Origin / direct-API denial (P12-05).
- No Playwright / browser storage / two-user cache (P12-07).
- No backup/restore continuity (P12-04).
- No ownership-404 audit event invention.
- No full DRIFT-29 / M-11 browser closure from this inventory.
