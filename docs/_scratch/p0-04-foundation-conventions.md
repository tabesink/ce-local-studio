# P0-04 Ownership, Privacy, Port, and State-Machine Evidence

Date: 2026-07-23  
Status: complete for the bounded P0-04 foundation convention package; vertical-slice implementation proof remains dependency-owned.

## Authority and completion boundary

The governing sources are `AGENTS.md`, `docs/database-schema.txt`, `docs/architecture/data-and-lifecycle.md`, `docs/architecture/security-operations-and-quality.md`, and `docs/architecture/production-adaptation-blueprint.md`.

P0-04 is a convention package. It closes four shared decisions needed by later application work:

1. authoritative resource ownership and isolation keys;
2. four privacy classes plus allowed browser, persistence, log/metric/audit/trace sinks;
3. the named outbound-port catalog and external-call transaction/reconciliation rule;
4. one uniform state-machine transition protocol.

It does not approve a production object-store technology, parser/provider behavior, runtime-controller topology, queue, or any exact feature transition absent from an owning contract. It does not claim the lifted services implement these rules.

## Lifted implementation inventory and disposition

| Lifted seam | Evidence | Disposition and owner |
| --- | --- | --- |
| runtime controller protocol | `services/domains.py:DomainRuntimeController` | retain the typed boundary concept; modify signatures/results for stable keys, typed uncertain outcomes, timeouts and generation reconciliation in P3 |
| retrieval protocol and provenance types | `services/evidence.py:RetrievalClient`, `InternalMappedEvidence` | retain and reverify the private-candidate concept; P6 proves authorization, one-domain scope, mapping and bounded failures |
| LightRAG protocol | `services/indexing.py:LightRAGClientProtocol` | modify to the P5 index/retrieval ports; native blocking/global behavior remains unapproved |
| parser and storage seams | parser errors/results and filesystem methods are embedded in `services/sources.py` | replace with explicit parser/object-store ports in P4; filesystem remains development-only |
| synthesis seam | `services/chat_turns.py:SynthesisStreamAdapter` returns deterministic placeholder sentences | replace with the typed bounded P7 adapter; fail closed until approved |
| operational telemetry seam | `services/tracing.py` wraps a disabled implementation with an allowlist | retain and reverify the private safety pattern under P8; it creates no Phase 1 product surface |
| dependency composition | no `context.py`, `adapters/` or `repositories/` package exists | add explicit composition and ports with P1 and owning verticals; directory presence alone will not earn credit |
| index states | lifted states use `submitting`, `accepted`, and `cancelling`, while the approved schema uses `processing` and `deleting` | modify through P5 migration/service/contract work; P0-04 does not bless the lifted vocabulary |
| turn states | lifted model omits approved `cancelled` | modify through P7 migration/SSE/cancel work |
| direct state assignment | state changes occur across large service modules | characterize only; P3-P7 must centralize owning transition services and prove lock/generation/audit behavior |

## Normative result

`docs/architecture/data-and-lifecycle.md` now contains:

- an exact ownership/access matrix, including no implicit administrator access to member conversations or Evidence;
- `public_safe`, `private_operational`, `content_sensitive`, and `secret` sink rules with propagation and fail-more-restrictive defaults;
- clock/ID, credential, object-store, parser, runtime-controller, LightRAG-index, retrieval, synthesis, and telemetry port responsibilities;
- seven ordered transition rules covering authority, transaction/lock, intent-before-call, leases/generations, uncertain outcomes, deletion fencing, conflicts, and server-truth projection;
- an explicit statement that lifted protocols/constants/state assignments are evidence only.

The package map points implementers to this expanded authority.

## Deterministic proof

`scripts/check-doc-phase-scope.sh` pins the ownership boundary, all four privacy classes, all nine outbound ports, the external-call rule, all seven state-machine rules, and the lifted-code completion boundary.

`scripts/tests/check-doc-phase-scope.sh` proves the checker fails when:

- administrator access is widened;
- `content_sensitive` is renamed/removed;
- adapters are allowed to authorize;
- uncertain outcomes are treated as terminal/retryable without reconciliation.

Focused results:

- live documentation governance: passed across 54 governed files;
- adversarial documentation fixtures: passed.

Full repository verification:

- Full root gate: passed against the final source state.
- Backend lint and 45 tests: passed.
- Generated OpenAPI/TypeScript live comparison and adversarial stale-artifact fixtures: passed.
- Frontend typecheck, 53 tests, and production build: passed.
- Backend Docker image build and Compose configuration: passed.
- Stable authority/checker manifest SHA-256: `82252cb3157835e41caff3ed0cafdfbe72516d7fa5aace5f4228487dbd69c70d`.

Known non-blocking inherited warnings remain: the Starlette TestClient/httpx deprecation, six high-severity npm audit findings, Node's module-type warning, and Next's middleware-file deprecation.
