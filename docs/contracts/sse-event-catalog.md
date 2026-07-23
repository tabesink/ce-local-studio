# SSE Event Catalog

Chat uses fetch-based Server-Sent Events. This contract replaces pilot `stage/evidence/token/done/error` payloads for the production target; adapters may translate old fixtures, but new clients implement only this envelope.

## Wire format and envelope

```text
id: evt_01J...
event: evidence.delta
data: {"schemaVersion":"1.0","eventId":"evt_01J...","turnId":"turn_01","sequence":4,"type":"evidence.delta","occurredAt":"2026-07-17T12:00:02Z","payload":{"items":[]}}

```

Every event is one UTF-8 `data` line followed by a blank line. Envelope field names are canonical camelCase on the wire. The JSON envelope is:

| Field | Rule |
| --- | --- |
| `schemaVersion` | `major.minor`; client rejects unsupported major |
| `eventId` | globally unique opaque ID; equals SSE `id` |
| `turnId` | authorized public turn ID; constant in one stream |
| `sequence` | positive integer, turn-scoped, strictly increasing from 1 |
| `type` | closed event type; equals SSE `event` |
| `occurredAt` | server UTC timestamp; display only, never ordering authority |
| `payload` | type-specific safe object; unknown fields ignored within a supported major |

SSE comment heartbeats (`: keep-alive`) are allowed and do not consume a sequence. `retry:` is advisory only; the client uses the bounded reconnect policy.

## Event types

| Type | Payload | Reducer effect |
| --- | --- | --- |
| `turn.accepted` | `{conversationId,clientRequestId,replay}` | create/attach running turn; clear stale transport error |
| `route.selected` | `{route,domain?}` | set `direct_llm` or `domain_rag`; domain is `{id,displayName}` safe summary |
| `retrieval.started` | `{attempt,maxAttempts}` | show bounded retrieval status; no reasoning text |
| `retrieval.completed` | `{result,evidenceCount}` | set `evidence_found` or `no_grounded_context` |
| `evidence.delta` | `{items:[EvidenceItem]}` | append unique ordered evidence; never replace another turn's panel |
| `answer.delta` | `{text}` | append answer text exactly once |
| `turn.completed` | terminal payload below | persist completed projection and stop reconnect |
| `turn.failed` | `{code,message,retryable,replay}` | set safe failed state and stop reconnect |
| `turn.cancelled` | `{code:"turn_cancelled",message,replay}` | set cancelled state and stop reconnect |
| `turn.redacted` | `{code:"turn_redacted",message,redactedAt}` | clear answer/evidence/citations/refs and invalidate open viewer |

`EvidenceItem` is defined by `document-and-evidence-contract.md` and contains only turn-scoped evidence ID, citation label, safe excerpt/labels, authorized document ref, and semantic anchor.

`turn.completed` payload:

```json
{
  "route": "domain_rag",
  "status": "completed",
  "stopReason": "grounded",
  "citations": [{"evidenceRefId":"ev_figure_01","citationLabel":"[1]"}],
  "acceptedRefs": [{"id":"accepted_01","kind":"source","order":1,"label":"Pump Manual","description":"Source"}],
  "budget": {"planStepCount":1,"retrievalOperationCount":1,"repairAttemptCount":0},
  "replay": false
}
```

Closed values:

- `route`: `direct_llm`, `domain_rag`.
- `status`: `completed`.
- `stopReason`: `direct_llm`, `grounded`, `no_grounded_context`, `evidence_only`, `turn_budget_exhausted`.
- accepted-ref `kind`: `source`, `evidence`, `template`.

## Legal sequences

```text
direct:   accepted -> route(direct_llm) -> answer* -> completed
grounded: accepted -> route(domain_rag) -> retrieval.started -> evidence+ -> retrieval.completed -> answer* -> completed
no hit:   accepted -> route(domain_rag) -> retrieval.started -> retrieval.completed(no_grounded_context) -> completed
evidence-only: grounded through evidence -> completed(evidence_only), no answer
failure:  any non-terminal prefix -> failed
cancel:   any non-terminal prefix -> cancelled
redact:   prior/active state -> redacted (supersedes all public derived content)
```

Requirements:

1. `turn.accepted` is sequence 1 and one `route.selected` follows.
2. Direct chat emits no retrieval or evidence events.
3. Domain RAG emits every non-empty evidence item before the first `answer.delta`.
4. Evidence order and citation labels are stable and unique within the turn.
5. An execution emits exactly one of completed/failed/cancelled. A later deletion may append one higher-sequence `turn.redacted`, which supersedes that terminal projection.
6. No event crosses a turn ID. Closing a connection neither completes nor cancels the turn.
7. Persist the safe event projection before acknowledging its sequence as resumable. Terminal state and terminal event commit atomically.

## Resume, replay, and cursor rules

- Start or attach: `POST /conversations/{conversationId}/turns:stream`.
- Resume/replay: `GET /conversations/{conversationId}/turns/{turnId}/events?after=N` where `N` is the last **applied** sequence; omit/zero for all currently public events.
- The server returns only sequences greater than `after`, except a redaction projection may omit superseded answer/evidence and return `turn.redacted`.
- Active reconnect waits with bounded exponential backoff and jitter, honors `Retry-After`, and stops after the UI enters an explicit offline state. User retry continues from the same applied cursor.
- Terminal replay is built only from persisted safe turn/evidence/ref state and marks terminal `replay:true`; it never calls retrieval, LightRAG, provider, or expired composer tokens.
- A cursor older than retained/reconstructable events returns `410 cursor_expired` with an authorized `terminalSnapshot` when available. The client replaces, rather than merges, its turn projection.
- Event retention is at least conversation retention. Purge and redaction remove forbidden public projections before content becomes inaccessible.

Example `410`:

```json
{
  "error": {"code":"cursor_expired","message":"The event cursor is no longer available.","requestId":"req_01"},
  "terminalSnapshot": {"turnId":"turn_01","status":"redacted","answer":null,"evidence":[],"citations":[]}
}
```

## Canonical client reducer

The same pure reducer consumes initial live, resumed live, and terminal replay fixtures.

1. Parse complete SSE frames across arbitrary byte chunk boundaries.
2. Validate envelope and supported major before applying payload.
3. Track `receivedSequence` separately from `appliedSequence`.
4. Ignore an exact duplicate `eventId`/sequence/payload digest.
5. On a sequence regression with a different event, or same sequence with different content, stop and report `stream_protocol_error`.
6. On a gap, apply nothing after the gap; reconnect using the last applied sequence.
7. For an unknown additive event in supported major, safely ignore its payload and advance the applied sequence.
8. Apply only if the current conversation/turn selection generation still matches; another turn's slow response cannot replace the Evidence Panel (`M-06`).
9. `turn.redacted` atomically clears derived content, closes the viewer, and prevents cached replay (`M-11`).

The reducer never treats socket close, HTTP success, token presence, or a locally complete-looking sentence as terminal.

## Transport headers

Successful streams return:

```text
Content-Type: text/event-stream; charset=utf-8
Cache-Control: private, no-store, no-transform
X-Accel-Buffering: no
Connection: keep-alive               # HTTP/1.1 only
```

Ingress/BFF must preserve chunks and propagate aborts. Pre-stream auth, validation, CSRF, ownership, domain eligibility, idempotency conflict, and capacity errors are canonical JSON, not half-open SSE. A failure after headers produces a safe event when the turn exists.

## Safety and fixtures

Events never include trace IDs, prompt/plan/reasoning text, raw source/template text, raw hits/scores, provider payloads, model/provider names, private source/block IDs, object keys, paths, runtime URLs, credentials, stack traces, or unsanitized errors.

Committed raw transcripts must cover direct success, grounded figure/text/table evidence, no grounded context, evidence-only, provider failure before evidence, cancel, disconnect/resume, duplicate delivery, sequence gap, terminal replay, cursor expiry, and post-completion redaction. Each transcript must produce the same final reducer state under 1-byte, random, and whole-frame chunking.
