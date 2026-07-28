# Legacy Gap Plan Bundle (2026-07-28)

Coding-agent entry index for folding the legacy comparative-gap audit into dependency-ordered Phase 1 implementation plans. Authority remains `AGENTS.md` → PRD/interaction → contracts → architecture/quality → `docs/master-build-plan.md` → these child plans → code.

## Decisions recorded

- Local-production topology: PostgreSQL + MinIO (S3-compatible) + private per-domain LightRAG + database-leased workers; only configured OpenAI/AWS model calls may leave the deployment; Ollama stays local.
- Filesystem object adapter remains development-only (P10-04).
- Upload orphan compensation and metric RAG-triad evaluation are deferred follow-ups (see brownfield addendum), not active tasks.
- Rejected legacy: Redis/RQ/Celery, JSON domain manifest, public runtime URLs, vendor upload authority, heuristic Evidence, Workspace/wiki, browser-selected providers/controllers, second streaming protocol.

## Dependency tiers

```text
Tier 1 (parallelizable)
  P1-07 idempotency + pagination
  P4-05 region provenance
  P7-06 synthesis isolation + turn heartbeat
  P10-04 MinIO object store
  P10-05 provider packaging
  P9-07 browser workflows  (after P4-05 + P11-02 credit)

Tier 2 (critical path)
  P5-04 real LightRAG runtime

Tier 3 (release)
  P12-04 backup/restore (needs P5-04 + P10-04)
  P12-05 ingress SSE/drain (needs P5-04 + P7-06)
  P12-06 immutable artifacts (needs P5-04 + P10-04 + P10-05)
  P12-07 browser E2E/capacity (needs P5-04 + P9-07 + P10-04 + P10-05)
  P12-08 production acceptance (needs P12-03..07)
```

## Gap → task → plan → evidence map

| Gap | Task | Plan | Prerequisites | Required evidence | Tail / deferred |
| --- | --- | --- | --- | --- | --- |
| Real LightRAG runtime | P5-04 | `docs/plans/2026-07-28-006-feat-p5-04-real-lightrag-runtime-plan.md` | P3-03,P5-03,P6-01,P10-03 | `docs/_scratch/p5-04-lightrag-real-runtime-{inventory,evidence}.md`; DRIFT-27 concurrency | P12-04/05/06/07 |
| Create-idempotency + pagination | P1-07 | `docs/plans/2026-07-28-007-feat-p1-07-idempotency-pagination-plan.md` | P1-06,P0-03 | `docs/_scratch/p1-07-idempotency-pagination-{inventory,evidence}.md` | UI residual none |
| Region provenance / M-04 | P4-05 | `docs/plans/2026-07-28-008-feat-p4-05-region-provenance-plan.md` | P4-03,P6-02,P9-03 | `docs/_scratch/p4-05-region-provenance-{inventory,evidence}.md` | P12-07 visual |
| Synthesis isolation + heartbeat | P7-06 | `docs/plans/2026-07-28-009-feat-p7-06-synthesis-isolation-heartbeat-plan.md` | P7-03,P7-04 | `docs/_scratch/p7-06-synthesis-isolation-heartbeat-{inventory,evidence}.md` | P12-05 drain |
| Contracted browser workflows | P9-07 | `docs/plans/2026-07-28-010-feat-p9-07-contracted-browser-workflows-plan.md` | P9-02..04,P4-05,P11-02 | `docs/_scratch/p9-07-contracted-browser-workflows-{inventory,evidence}.md` | P12-07 Playwright |
| MinIO object store | P10-04 | `docs/plans/2026-07-28-011-feat-p10-04-minio-object-store-plan.md` | P10-03,P4-01 | `docs/_scratch/p10-04-minio-object-store-{inventory,evidence}.md`; DRIFT-15 | P12-04/06/08 |
| Provider packaging | P10-05 | `docs/plans/2026-07-28-012-feat-p10-05-provider-packaging-plan.md` | P4-03,P7-03,P10-03 | `docs/_scratch/p10-05-provider-packaging-{inventory,evidence}.md` | P12-06/07 |
| Backup/restore + rebuild | P12-04 | `docs/plans/2026-07-28-005-feat-p12-04-backup-restore-drills-plan.md` | P5-04,P10-04,P12-01 | `docs/_scratch/p12-04-backup-restore-{inventory,evidence}.md` | P12-08 digests/KMS |
| Ingress SSE/drain | P12-05 | `docs/plans/2026-07-28-013-feat-p12-05-deployed-ingress-sse-drain-plan.md` | P5-04,P7-06,P9,P12-02 | `docs/_scratch/p12-05-deployed-ingress-{inventory,evidence}.md` | P12-08 |
| Immutable artifacts | P12-06 | `docs/plans/2026-07-28-014-feat-p12-06-immutable-artifact-manifest-plan.md` | P0,P5-04,P10-04,P10-05,P12-02 | `docs/_scratch/p12-06-immutable-artifact-{inventory,evidence}.md` | P12-08 |
| Browser E2E/capacity | P12-07 | `docs/plans/2026-07-28-015-feat-p12-07-browser-e2e-capacity-plan.md` | P5-04,P9-07,P10-04,P10-05,P12-02,P12-03 | `docs/_scratch/p12-07-browser-e2e-capacity-{inventory,evidence}.md` | B0 complete |
| Production acceptance | P12-08 | `docs/plans/2026-07-28-016-feat-p12-08-production-acceptance-plan.md` | P12-03..07 | `docs/_scratch/p12-08-production-acceptance-{inventory,evidence}.md` | Release decision |

## Agent execution rules

1. One plan → one inventory → units in dependency order → one evidence doc → tracker/DRIFT update.
2. Credit green existing proofs; do not rebuild P4-03/P6/P7-03 fixture altitude or P12-03 API adversarial suites unless a gap test fails.
3. Hard-stop if a slice needs an unapproved browser field, Redis/queue, public runtime URL, filesystem-as-production-store, or Path 2 migration.
4. Register every new plan file in `docs/phase-scope-manifest.md` before claiming documentation gates green.
