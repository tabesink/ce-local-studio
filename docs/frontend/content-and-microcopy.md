# Content and Microcopy Contract

Member-chat capability language must reference `docs/prd.md#closed-phase-1-chat-capability-manifest`. This document defines labels and messages only; it must not restate or expand the capability set.

UI copy is part of behavior: it must name product truth without exposing implementation truth. Use short, active sentences and the vocabulary below.

## Canonical vocabulary

| Use | Meaning | Do not substitute |
| --- | --- | --- |
| Context Engine | product | Local Studio, RAG console |
| Knowledge Domain | isolated curated corpus/runtime | workspace, index, database |
| Library | document browsing route | file system, storage bucket |
| Source Document | governed uploaded source | blob, object key, raw file |
| Evidence | safe turn-scoped support for an answer | chunk, block ID, context dump |
| Citation | answer marker pointing to Evidence | URL, source path |
| Conversation / Turn | durable member chat / one question-answer attempt | session / run |
| Operation | durable asynchronous admin work | job ID, worker task |
| Reference picker | governed source/evidence/template selection | Evidence Panel, AI writer |
| Evidence Panel | evidence for exactly one selected turn | Reference picker, source browser |

Member copy says what the person can do. Administrator copy may name lifecycle and operations, but never Docker, LightRAG paths, database rows, credentials, queues, provider payloads, or stack traces.

## State labels

API enum values map through one exhaustive function. Unknown values render `Unknown state` and a safe request ID; never title-case an arbitrary server string.

| Product state | Label | Supporting copy |
| --- | --- | --- |
| stopped | Stopped | Not available for questions. |
| starting/queued | Starting | An operation is waiting or running. |
| running/eligible | Available | Ready for authorized questions. |
| preparing | Preparing | Extracting governed document content. |
| indexing | Indexing | Making prepared content available for retrieval. |
| failed | Failed | The operation did not complete. |
| cancelling | Cancelling | Waiting for the current operation to stop. |
| deleting | Deleting | Unavailable now; cleanup is continuing. |
| reconnecting | Reconnecting | The answer is still running. |
| redacted | Answer redacted | A supporting source is no longer available. |

Avoid `Done` when the state is `accepted`, `queued`, or remote cleanup remains.

## Empty, loading, and unavailable copy

| Surface | Empty | Safe unavailable |
| --- | --- | --- |
| Conversations | `Start a conversation to ask a question.` | `Conversation is no longer available.` |
| Domains | `No Knowledge Domains are available.` | `Domain list could not be loaded.` |
| Domains Settings (admin) | same empty as Domains; Deploy remains available when product allows | same load failure; never “Knowledge Graphs” |
| Evidence | `No evidence was returned for this turn.` | `Evidence no longer available.` |
| Library | `No Source Documents in this Knowledge Domain.` | `Document is no longer available.` |

Loading labels name the object (`Loading conversation…`, `Opening document…`) and do not promise an outcome. Skeletons normally need no visible text if the route heading is present.

## Error pattern

Every actionable error has three parts:

```text
<What did not happen>. <What the user can do next>.
Request ID: <safe request ID>
```

| Code/condition | Canonical copy |
| --- | --- |
| invalid login | `Sign-in failed. Check your credentials and try again.` |
| `domain_required` | `Choose a Knowledge Domain for this question.` |
| `domain_not_query_eligible` | `This Knowledge Domain is no longer available. Choose another domain.` |
| `idempotency_conflict` | `This submission changed after it was first sent. Review the draft and submit again.` |
| `stale_revision` | `This item changed elsewhere. Review the current version before saving.` |
| `operation_conflict` | `Another operation already changed this item. The latest state is shown.` |
| Domains deploy start-failed-keep | `The Knowledge Domain was created, but start did not finish. Try Start again.` |
| `cursor_expired` | `Live history expired. Loading the saved answer.` |
| rate limit | `Too many requests. Try again <server-provided time>.` |
| unauthorized target | `This item is unavailable or you do not have access.` |
| generic dependency | `The request could not be completed. Try again.` |

Never guess a retry time, reveal account existence, echo an unsafe upstream message, or say `Contact support` unless an actual support route is configured.

## Actions and confirmations

- Buttons use verb + object: `Start domain`, `Retry indexing`, `Delete source`, `Save settings`.
- Busy labels describe accepted local intent only: `Submitting…`, `Requesting stop…`, `Uploading…`.
- Cancel closes an unsubmitted dialog; `Cancel operation` requests a server transition. Do not label both `Cancel` in one surface.
- Destructive confirmation names the object and immediate/downstream effect. The destructive button repeats the action, not `Confirm`.
- Secret fields say `Credential configured` and `Replace credential`; never use fake masked values that imply the stored secret was returned.

## Junior examples

Bad: `Vector DB 500: collection missing at /data/domain-7.`  
Good: `The Knowledge Domain is unavailable. Try starting it again. Request ID: req_…`

Bad: show `Deleted` immediately after click.  
Good: show `Requesting deletion…`, then `Deleting` from the accepted operation DTO.

Bad: `No context, answering anyway.`  
Good: `I could not find evidence in this Knowledge Domain, so I cannot provide a grounded answer.`

## Writing and test rules

- Sentence case, no exclamation marks, no blame, no unexplained acronyms.
- Labels must remain meaningful out of visual context for screen readers.
- Dates use the user's locale plus an exact timestamp affordance; operation IDs are copyable only when approved safe refs.
- Snapshot copy by stable message key, not by duplicating prose across components.
- Contract tests enforce exhaustive enum/error mappings; privacy tests scan rendered copy for paths, URLs, secrets, raw errors, and private IDs.

Traceability: M-01 through M-11, A-01 through A-10, A-13, and C-01 through C-05.
