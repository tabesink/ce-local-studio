# P6-01 Scoped Retrieval and Provenance Inventory

Date: 2026-07-25

Owner: P6-01

Status: IN_PROGRESS

Requirements and cases: FR-05; A-08; C-01; C-02; DRIFT-27; P6-01 in
`docs/master-build-plan.md`; `docs/contracts/document-and-evidence-contract.md`;
`docs/architecture/data-and-lifecycle.md`.

## Scope

- Establish one private retrieval port for one server-selected, running,
  runtime-ready domain with at least one current eligible source.
- Bound admission, the complete retrieval deadline, candidate count, and
  individual/aggregate candidate bytes before provenance parsing.
- Map only exact schema-v2 block envelopes to current selected-domain Source
  Blocks, comparing frozen pre-call identities in one post-call SQL snapshot.
- Keep question text, raw hits, provider payloads, block IDs, runtime details,
  and index identities behind the private service boundary.

## Out of scope

- P6-02 public Evidence DTOs, excerpts, labels, opaque refs, anchors, ordering,
  and HTTP failure projection.
- P7 intent classification, chat persistence, grounded refusal, and SSE.
- P8 broad sink/privacy telemetry proof and P9 browser Evidence/document UX.
- A second retrieval stack, provider retries, fuzzy provenance, or ungrounded
  fallback.

## Disposition register

| Surface / call site | Current evidence | Disposition | P6-01 action and proof |
| --- | --- | --- | --- |
| `services/indexing.py::render_blocks_to_lightrag_handoff` | P5 schema-v1 source header plus unversioned block markers | modify | Render a self-contained schema-v2 first-line block envelope; renderer/local/native fixtures prove exact preservation. Existing schema-v1 ready content must be reindexed, never heuristically accepted. |
| `services/indexing.py::LightRAGClientProtocol` | Index lifecycle and retrieval are conflated | modify | Remove retrieval from the lifecycle protocol; local/native adapters may structurally implement both private protocols. |
| `services/indexing.py::{LocalLightRAGIndexClient,LightRAGClient}.retrieve` | Local result is unbounded; native top-k is adapter-only; native lock wait is outside its async timeout | modify | Enforce adapter-side count/byte limits and one retrieval deadline including bounded admission/lock wait/execution/cleanup; focused saturation, timeout, malformed-result, and overrun tests. |
| `services/indexing.py::source_is_query_eligible` | P5-03 proves current prepared/ready/request/domain eligibility | retain-and-reverify | Reuse eligibility predicates; freeze domain/source generations and index identities before the call and repeat them in the joined post-call mapping query. |
| `services/evidence.py::resolve_available_domain` / `eligible_sources_for_domain` | Correct broad intent, but returns live ORM entities later reused across a commit | modify | Produce a private frozen retrieval scope instead of treating `expire_on_commit=False` objects as freshness evidence. |
| `services/evidence.py::parse_ce_block_marker` | Finds one unversioned token anywhere in provider text | replace | Parse only the anchored schema-v2 first line and reject additional reserved provenance tokens in the body. |
| `services/evidence.py::map_retrieval_hits_to_internal_evidence` | Per-hit `db.get()` can reuse stale identity-map rows and multiple READ COMMITTED snapshots | replace | Bound/deduplicate identities, then use one joined SQL statement containing every frozen domain/source/block predicate; preserve adapter order and assign dense survivor rank. |
| `services/evidence.py::retrieve_scoped_evidence` | Calls the conflated client and directly creates a partial public projection | modify | Delegate private retrieval/mapping through the P6 port while keeping route response behavior unchanged until P6-02. |
| `services/chat_turns.py::P6RetrievalPort` and wrapper | P7-owned scaffold duplicates a concrete P6 seam before chat orchestration exists | defer | Remove/reduce duplication only as mechanically required; P7 remains the owner of chat orchestration. |
| `api/routes.py` evidence route / `main.py` registration | Lifted partial public Evidence contract | defer | No behavioral edit in P6-01; P6-02 owns projection, route errors, and approved public refs. Generated contracts must remain unchanged. |
| `tests/test_lightrag_renderer_adapter.py` | P5 renderer/timeout/local lifecycle proof | retain-and-reverify | Update private handoff expectations and add exact schema-v2/local/native preservation and adapter-bound regression proof. |
| Focused P6 tests | No dedicated scoped retrieval unit or PostgreSQL race suite | add | Add `test_scoped_retrieval.py` and `test_postgres_scoped_retrieval.py`, including hostile markers, byte/count bounds, isolation, and barrier-driven stop/restart plus reindex/new-ready races. |
| Application wiring | `index_client_from_settings` returns the conflated lifecycle protocol | modify | Preserve construction while type-checking lifecycle and retrieval at their owning boundaries; no browser-selected upstream or public field. |

## Stop conditions

1. Native LightRAG must preserve the exact schema-v2 envelope with the block
   content. If it does not, stop instead of parsing source text heuristically.
2. If P6-01 needs a new public DTO field, endpoint, or error code, stop for the
   P6-02 contract owner.
3. SQLite or mocked sessions cannot close the freshness requirement. P6-01
   remains incomplete without PostgreSQL 16 barrier evidence.

## Residual owners

- P6-02: safe public Evidence projection, member retrieval route semantics, and
  document/evidence refs.
- P7: bounded repair/orchestration, persistence, grounded refusal, and SSE.
- P8: cross-sink privacy and operational-safety breadth.
- P9: Evidence inspector and governed source navigation.
- P10/P12: deployed capacity and production evidence beyond this internal
  process-level adapter safety boundary.
