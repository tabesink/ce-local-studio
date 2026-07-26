# P6-02 Stateless Evidence Projection Inventory

Date: 2026-07-26

Owner: P6-02

Status: DONE - implemented and proven 2026-07-26

Requirements and cases: FR-05; M-02; M-03; C-01; C-02; P6-02 in
`docs/master-build-plan.md`; `docs/contracts/http-api-catalog.md`;
`docs/contracts/dto-schema-catalog.md`;
`docs/contracts/document-and-evidence-contract.md`.

## Scope

- Close the member/admin stateless one-domain Evidence retrieval boundary.
- Project only canonical, mapped, currently authorized Evidence through closed
  camelCase DTOs with response-scoped citations and no Evidence ID.
- Represent only provable page/section anchors; never fabricate a page or
  expose a region through this stateless endpoint.
- Translate all retrieval failures to the approved safe public envelope while
  keeping the operation read-only and `private, no-store`.

## Disposition register

| Surface / call site | Prior evidence | Disposition | P6-02 result |
| --- | --- | --- | --- |
| `RetrievalEvidenceRequestDto` | Length validation ran before whitespace normalization | modify | Normalize first, then enforce the closed 1..2,000-character bound. |
| Stateless Evidence anchor | Reused durable `EvidenceAnchorDto`, which admitted a region fallback absent from the approved stateless behavior | replace | Add closed `RetrievalEvidenceAnchorDto` with one-based page, optional bounded section label, and only `section`/`page` fallback. |
| `RetrievalEvidenceResponseDto` | Result and Evidence cardinality could contradict each other | modify | Enforce non-empty Evidence for `evidence_found` and an empty list for `no_grounded_context`. |
| `services/evidence.py` projection | P6-01 private mapped rows and terminal fences existed | retain-and-reverify | Preserve canonical excerpt/labels/opaque document ref, deterministic first-valid ordering, block deduplication, dense citations, conservative anchors, and terminal reauthorization. |
| `services/chat_turns.py::P6RetrievalPort` | Shared the P6 retrieval seam with the P7 scaffold | retain-and-reverify | Characterization proof confirms durable turn Evidence linkage and safe private failure translation remain intact; P7 still owns orchestration and replay. |
| Evidence HTTP route | Lifted request/response shapes and partial error handling | modify | Bind authoritative DTOs, validate the final response, exhaustively map safe errors, and return private no-store success/failure responses with request IDs. |
| OpenAPI, public JSON Schema, TypeScript client | Generated from authoritative DTO/route registration | modify | Regenerate all affected artifacts and prove byte-equivalent regeneration. |
| Endpoint persistence and logs | No endpoint-specific no-mutation/privacy proof | add | Snapshot all database table counts after startup, assert request-time equality, and scan captured logs for question, excerpt, label, and dependency sentinels. |
| Durable Evidence IDs, replay, redaction, governed document resolution | Owned by later phases | defer | P7 remains the sole owner of turn persistence/orchestration/replay/redaction; P9 owns browser Evidence/document navigation. |

## Explicit exclusions

- No persistent or ephemeral public Evidence ID is created.
- No multi-domain retrieval, direct-model fallback, retry loop, or new
  retrieval stack is added.
- No document byte/location endpoint, composer ref, SSE event, or browser
  capability is introduced.
- P8 retains system-wide audit/log/trace/metric/privacy and resilience breadth;
  this slice proves only sinks reached by the stateless endpoint.

## Residual owners

- P7: intent classification, bounded orchestration/repair, durable turn
  Evidence, grounded refusal/evidence-only completion, SSE replay, and
  redaction.
- P8: system-wide audit coverage, safe observability, cross-sink privacy scans,
  load, and resilience evidence.
- P9: Evidence inspector, authorized source navigation, and governed document
  rendering.
- P10/P12: deployed topology, multi-replica/load, recovery, and production
  release proof.
