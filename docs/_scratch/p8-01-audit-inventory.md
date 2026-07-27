# P8-01 Transactional Audit Allowlist Denial Privacy Inventory

Date: 2026-07-27

Owner: P8-01

Status: DONE — inventory + U2–U4 migrations/tests evidenced 2026-07-27

Requirements and cases: FR-09; C-02; C-05; DRIFT-20; DRIFT-29 audit/privacy half

Plan: `docs/plans/2026-07-27-006-feat-audit-allowlist-denial-privacy-plan.md`

## Scope

Inventory every closed `AUDIT_EVENT_NAMES` entry and every production
`AuditService.record` / `commit_protected_mutation` call site. Assign a
disposition class before code moves. P8-01 owns call-site allowlist coverage,
contracted denial matrix (including mandatory `require_admin` audit-failure
harden), and adversarial privacy scans of `audit_events` rows only.

Out of scope: P8-02 structured logs/metrics; P8-03 health/cross-sink privacy
gate; Phase 2 audit-read/export UI; inventing ownership-404 denial events;
wrapping external I/O inside `commit_protected_mutation`.

## Disposition classes

| Class | Meaning |
| --- | --- |
| `protected-helper` | Already on / will use `commit_protected_mutation` |
| `migrate` | Request-path single-commit pair; move onto helper in U2 |
| `denial-only` | Authz denial audit; no product mutation; U3 harden |
| `worker-terminal` | Worker/lifecycle terminal audit; exempt from helper wrap |
| `nested-redaction-flush` | `record` flush inside outer protected txn (`commit=False`) |
| `external-call-split` | Intent commit → external work → terminal audit |
| `open-txn-object-put` | Flush product+audit → object I/O → single commit |
| `orphan-reserved` | Closed vocabulary; no Phase 1 product writer |
| `retain-absence` | Keep Phase 1 absence (no audit-read) |

## Closed event register

| Event | Writer(s) | Actor | Disposition | P8-01 action |
| --- | --- | --- | --- | --- |
| `runtime_settings.provider_config_rotated` | `runtime_config._commit_runtime_mutation` | HTTP admin | `protected-helper` | retain; privacy scan fixture |
| `runtime_settings.model_profile_created` | same | HTTP admin | `protected-helper` | retain |
| `runtime_settings.model_profile_updated` | same | HTTP admin | `protected-helper` | retain |
| `runtime_settings.model_profile_deleted` | same | HTTP admin | `protected-helper` | retain |
| `runtime_settings.defaults_updated` | same | HTTP admin | `protected-helper` | retain |
| `domain.created` | `domains._finish_operation` after controller | worker/HTTP lifecycle | `external-call-split` + terminal helper | retain pattern; do not wrap controller |
| `domain.started` | `_finish_operation` | lifecycle | `external-call-split` + terminal helper | retain |
| `domain.stopped` | `_finish_operation` | lifecycle | `external-call-split` + terminal helper | retain |
| `domain.delete_queued` | `enqueue_delete_domain` | HTTP admin | `protected-helper` | retain; nested redaction proof |
| `domain.delete_succeeded` | `_finish_operation` and/or DomainDeleteWorker `~1095` | worker | `worker-terminal` / helper on finish path | exempt worker ad-hoc; characterize |
| `domain.delete_failed` | `_fail_operation` | worker | `worker-terminal` | exempt; ad-hoc record+commit |
| `source.uploaded` | `upload_source_bytes` | HTTP admin | `open-txn-object-put` | exempt; forbid helper wrap |
| `source.preparation_retried` | `retry_source` / prep retry | HTTP admin | `migrate` | U2 helper + IntegrityError→409 |
| `source.preparation_cancelled` | `cancel_source` | HTTP admin | `migrate` | U2 helper |
| `source.deleted` | none (product) | — | `orphan-reserved` | document only |
| `source.delete_queued` | `enqueue_delete_source` | HTTP admin | `protected-helper` | retain; nested redaction |
| `source.delete_succeeded` | SourceDeleteWorker | worker | `worker-terminal` | exempt |
| `source.delete_failed` | SourceDeleteWorker | worker | `worker-terminal` | exempt |
| `source.index_retry_queued` | `retry_source_index` terminal pair | HTTP admin | `migrate` | U2: migrate terminal record+commit after optional remote delete |
| `source.index_cancelled` | `cancel_source_index` terminal pair | HTTP admin | `migrate` | U2: migrate final cancelled+audit commit; keep intermediate CANCELLING commit + remote outside helper |
| `chat.turn_redacted` | `_redact_turns` | nested in delete fence | `nested-redaction-flush` | retain flush-only; prove outer rollback |
| `conversation.created` | `conversations.create` | HTTP member | `protected-helper` | retain; privacy title sentinel |
| `conversation.renamed` | `conversations.rename` | HTTP member | `protected-helper` | retain; privacy title sentinel |
| `conversation.deleted` | `conversations.delete` | HTTP member | `protected-helper` | retain |
| `security.admin_route_denied` | `require_admin` | HTTP member/ex-admin | `denial-only` | U3 matrix + KTD8 fail-closed harden |
| `user.disabled` | tests / synthetic helper only | — | `orphan-reserved` | keep P1-06 synthetic proof; no product API |
| `user.enabled` | none | — | `orphan-reserved` | document only |

## Call-site disposition register

| Surface | Current evidence | Disposition | P8-01 action |
| --- | --- | --- | --- |
| `conversations.py` create/rename/delete | `commit_protected_mutation` always | `protected-helper` | retain; privacy fixtures |
| `runtime_config._commit_runtime_mutation` | helper when context present; None bypass | `protected-helper` | retain; assert HTTP routes pass context |
| `domains._finish_operation` success | helper when event+context | `external-call-split` terminal | retain |
| `domains._fail_operation` | ad-hoc record+commit | `worker-terminal` | exempt |
| `domains.enqueue_delete_domain` | helper + nested redaction | `protected-helper` + `nested-redaction-flush` | retain; PG rollback proof |
| DomainDeleteWorker succeed path `~1095` | ad-hoc record | `worker-terminal` | exempt |
| `sources.upload_source_bytes` | flush+record → put_key → commit | `open-txn-object-put` | exempt |
| `sources` prep retry | record+commit; IntegrityError→409 | `migrate` | U2 |
| `sources` prep cancel | record+commit | `migrate` | U2 |
| `sources.enqueue_delete_source` | helper | `protected-helper` + nested | retain |
| SourceDeleteWorker terminals | ad-hoc record+commit | `worker-terminal` | exempt |
| `indexing.retry_source_index` | optional remote then record+commit | `migrate` (terminal) | U2 |
| `indexing.cancel_source_index` | intermediate commit → remote → record+commit | `migrate` (terminal only) | U2 |
| `chat_turns._redact_turns` | record flush; commit optional | `nested-redaction-flush` | retain |
| `dependencies.require_admin` | record+commit then 403 | `denial-only` | U3 harden to 503 on audit failure |
| Public audit read APIs | absent | `retain-absence` | keep observability scope tests green |

## Intentional non-audit denial paths

| Path | Public response | Audit | Rationale |
| --- | --- | --- | --- |
| Ownership / unknown conversation | identical `404` | none | non-disclosure; no probe oracle |
| Unauthenticated / disabled / idle session | `401` | none | not contracted denial-audit event |
| CSRF / Origin / Host ingress | `403 forbidden` | none | ingress security, not admin-route denial |
| State conflicts | `409` | none | not authz denial |
| Chat `domain_required` | `422` | none | intent gate, not authz |

`security.admin_route_denied` field freeze: actor, outcome, safe_error_code,
request correlation only — no resource-existence `target_id`.

## Approved private audit identifier shapes

Allowed in private sink for privacy scanner:

- `actor_user_id` (user UUID)
- `target_id` shapes already used by writers: conversation/turn `public_ref`,
  domain id, source id, operation id (inventory-approved)
- `request_id` / `trace_id` correlation strings

Forbidden even if classified `private_operational` elsewhere: object keys,
runtime/controller/provider URLs or identifiers, block IDs, filesystem paths,
credentials, tokens, prompts, answers, excerpts, titles/filenames outside
`ALLOWED_AUDIT_METADATA_KEYS`.

## Retained invariants

- Append-only `audit_events`; no Phase 1 read/export.
- Protected mutations and required audit commit together or roll back together.
- Audit failure → `503 audit_unavailable` with no product change (including
  denial-audit failure per KTD8).
- Closed event/actor/outcome/metadata allowlists.
- Nested redaction audits stay flush-only inside outer delete fence txn.

## Gaps this task closes

1. Disposition register for every closed event and production writer.
2. Migrate prep retry/cancel and index retry/cancel terminal pairs onto helper.
3. Denial matrix + mandatory `require_admin` audit-failure harden.
4. Adversarial `audit_events` privacy scans.
5. DRIFT-20 / DRIFT-29 audit residual notes after proof (U4).

## Evidence design

See U4 / `docs/_scratch/p8-01-audit-evidence.md` (after verification):

- Focused unit matrix + privacy tests
- Disposable PostgreSQL 16 for denial, nested delete rollback, helper rollback
- Keep `test_phase_one_observability_scope.py`, `test_postgres_audit.py`,
  `test_audit_service.py` green
