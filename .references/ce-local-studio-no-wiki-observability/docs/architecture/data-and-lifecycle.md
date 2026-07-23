# Data and Lifecycle Architecture

## Domain lifecycle

```text
create -> stopped -> start operation -> running
running -> stop operation -> stopped
stopped/running -> deleting -> delete worker -> removed
```

Every control operation records its generation. Workers may complete only while their lease and generation remain current. Delete first makes the domain ineligible, then removes remote/runtime and local derived state, redacts dependent chat state, and finally removes authoritative domain rows.

## Source and index lifecycle

```text
upload -> pending -> prepare operation -> prepared
prepared + domain running -> index queued -> processing -> ready
processing -> failed | cancelled | ready
any live source -> deleting -> redaction/invalidation -> remote/local removal
```

Preparation produces stable ordered Source Blocks. Indexing renders a versioned handoff containing local provenance markers, then maps retrieval results back through those markers. Generation counters and content hashes make retry safe and prevent stale completions.

## Grounded turn lifecycle

1. Authorize conversation ownership and validate `client_request_id`.
2. Resolve and validate composer refs; compute a stable fingerprint.
3. Determine effective route: explicit domain means `domain_rag`; otherwise the server intent gate may allow `direct_llm`.
4. Persist a running turn with private trace ID and bounded-operation counters.
5. For domain RAG, validate domain/source eligibility, retrieve and map Evidence, then synthesize only from the authorized context.
6. Stream safe plan/status/evidence/token/terminal events.
7. Persist terminal answer, stop reason, safe error, Evidence refs, and accepted composer refs.
8. On an identical terminal retry, replay persisted state without external calls; mismatched inputs return conflict.

## Redaction invariant

Deleting any cited source or the selected domain redacts the whole derived turn. Preserve `user_message`; set turn status/stop reason to redacted; clear assistant answer and public evidence labels/excerpts; retain redacted evidence rows for internal audit. Public mappers treat them as absent.

## Data classification

- **Public/safe:** opaque product IDs where approved, display labels, safe excerpts, status enums, timestamps, safe error codes/messages.
- **Private operational:** source/block IDs, trace IDs, target linkage, storage/runtime identifiers, controller details.
- **Secret/content-sensitive:** credentials, raw tokens, source binaries/text, assembled prompts, raw provider/LightRAG payloads, stack traces. Never expose or place in logs/audit/traces.
