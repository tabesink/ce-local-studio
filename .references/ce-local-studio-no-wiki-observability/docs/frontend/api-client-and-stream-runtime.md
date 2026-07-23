# API Client and Stream Runtime

The browser calls same-origin `/api/v1` only. FastAPI owns identity, authorization, idempotency, routing, and terminal state; Next BFF handlers forward approved cookies/headers and strip caller-supplied infrastructure or identity headers.

## Package shape

```text
src/lib/api/generated/       OpenAPI-generated DTOs and endpoint functions
src/lib/api/core/            request, error, CSRF, timeout, response validation
src/lib/api/capabilities/    auth, domains, sources, chat, context, operations
src/lib/stream/              SSE parser, schemas, cursor, reducer, reconnect
src/features/*/api.ts        thin capability-specific adapters only
```

Do not copy Local Studio's browser-selected backend URL, API-key storage, fallback controller, or permissive legacy SSE normalization. Reuse its modular-client and canonical-reducer patterns only.

## HTTP request contract

- Base path is compile-time same-origin `/api/v1`; browser code cannot override it.
- Always send `credentials: "include"`, `Accept: application/json`, and a generated request ID where contracted.
- Unsafe methods send the session-bound double-submit CSRF token from the approved transient accessor. Never persist it.
- JSON responses are decoded against generated/runtime schemas. Invalid success payloads become `contract_violation` and include the server request ID in diagnostics.
- All calls accept an `AbortSignal`; header/body timeouts are capability-specific and explicit.
- Error projection is `{status, code, message, requestId, retryAfter?, fieldErrors?}`. Render only the safe `message`; never expose response HTML, stack text, or upstream payloads.

## Retry matrix

| Request | Automatic behavior |
| --- | --- |
| `GET` list/detail | at most 2 retries for network/502/503/504; exponential backoff + jitter |
| login/logout | no automatic replay |
| ordinary unsafe mutation | no replay unless endpoint contract declares stable idempotency |
| operation start/retry/cancel | retry only with unchanged idempotency key and fingerprint |
| stream start before turn ID known | repeat the same POST ID/fingerprint after uncertainty |
| stream after turn ID known | resume with GET; never restart provider work |
| `409`, `401`, `403`, `404`, validation | never automatically retry |
| `429` | honor bounded `Retry-After`; keep user intent |

Backoff is `min(8000, 250 * 2^attempt) + random(0..250)` ms, maximum five resume attempts before showing a manual Retry control. Online/visibility changes may trigger one immediate attempt. Tests inject deterministic jitter.

## Turn identity and fingerprint

Create `clientRequestId` once per effective draft. The server computes the canonical SHA-256 fingerprint from UTF-8 canonical JSON containing conversation safe ref, normalized message, effective route/domain, and ordered resolved composer refs; CSRF and timestamps are excluded. The browser sends no fingerprint field and must reuse the identical request body when retrying an uncertain start. Same `(conversation, clientRequestId, server-computed fingerprint)` attaches/replays; a changed effective input with the same ID must surface `409 idempotency_conflict`.

## SSE envelope and parser

Every event must validate:

```ts
type Envelope = {
  schemaVersion: string;
  eventId: string;
  turnId: string;
  sequence: number;
  type: string;
  occurredAt: string;
  payload: unknown;
};
```

The incremental parser supports CRLF/LF, multiple `data:` lines, comments/keepalive, chunk splits inside UTF-8/code points, and a final complete frame. It rejects oversized frames, invalid JSON, unsupported major versions, missing fields, and cross-turn frames. Unknown additive event types are safely ignored but their sequence is committed so reconnect does not loop.

## Canonical lifecycle reducer

```text
direct:   turn.accepted -> route.selected -> answer.delta* -> turn.completed
grounded: turn.accepted -> route.selected -> retrieval.started -> evidence.delta+
          -> retrieval.completed -> answer.delta* -> turn.completed
no hit:   turn.accepted -> route.selected -> retrieval.started
          -> retrieval.completed(no_grounded_context) -> turn.completed
failure/cancel: any non-terminal prefix -> turn.failed | turn.cancelled
```

Evidence-only and later-redaction sequences follow `contracts/sse-event-catalog.md`; that catalog is canonical when a summary here omits a legal branch.

| Event | Projection effect |
| --- | --- |
| `turn.accepted` | bind authoritative turn ID; commit user message |
| `route.selected` | set `direct_llm` or `domain_rag`; never infer in browser |
| `retrieval.started` | show bounded activity; no planning text |
| `evidence.delta` | upsert ordered safe evidence for this turn |
| `retrieval.completed` | commit `evidence_found` or `no_grounded_context` and its evidence count |
| `answer.delta` | append exactly once to the active answer |
| terminal event | replace status/error/citations with authoritative terminal projection |

Reducer input is identical for initial POST, resumed GET, and durable replay fixtures. UI-specific animations consume reducer output; they do not alter canonical text.

## Cursor algorithm

Maintain `receivedSequence` and `appliedSequence` per turn. Only `appliedSequence` is a resume cursor.

1. If `eventId`, sequence, and payload digest exactly match an applied event, ignore it as a duplicate.
2. If `sequence <= appliedSequence` but the event is not that exact duplicate, stop with `stream_protocol_error`.
3. If `sequence > appliedSequence + 1`, apply nothing after the gap; close and resume after `appliedSequence`.
4. Validate and reduce the event, then atomically set `appliedSequence = sequence`.
5. EOF without terminal state sets `reconnecting`; it never sets completed/failed.
6. Resume `GET .../events?after=<appliedSequence>` until terminal, user leaves runtime ownership, or policy exhausts.

On `410 cursor_expired`, validate and apply an authorized terminal snapshot if present. Otherwise fetch the conversation/turn snapshot. If neither can establish terminal truth, show `History is no longer available` without inventing an answer.

## Cancellation and ownership

Unmount/navigation aborts the browser reader but not server work. A product Cancel button calls only a contracted cancel endpoint and remains pending until `turn.cancelled`. Each tab may attach independently; server ownership and idempotency prevent mixed turns. A stream controller key includes identity epoch, conversation ref, and turn ref.

## Required fixtures and tests

- parser: byte-by-byte UTF-8, multiline data, keepalive, malformed/oversized frame;
- reducer: full lifecycle, direct route without evidence, refusal with no evidence, redaction snapshot;
- cursor: duplicate overlap, gap, conflicting sequence, unknown event, disconnect before terminal;
- transport: POST uncertainty, resume, `410`, `409`, `401`, rate limit, logout midstream;
- deployed ingress: first event flushes incrementally and headers disable buffering/cache;
- concurrency: C-01 evidence/turn isolation and M-10 one-provider-call behavior.

Traceability: M-03, M-06, M-07, M-09 through M-11, A-04, C-01, and C-04.
