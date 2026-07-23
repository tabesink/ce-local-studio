# Interaction Behavior PRD

This document is the executable role-play contract for Context Engine. It defines observable user/admin behavior and atomic state transitions. When UI intuition conflicts with a case here, this document wins unless the product contract is explicitly amended.

## Case format and implementation rule

Each case specifies:

- **Given:** authoritative preconditions.
- **When:** one user intent.
- **Then:** committed server state and observable UI result.
- **Race/failure:** required behavior under concurrency, retry, stale state, or dependency failure.

The backend performs authorization and transition checks inside the committing transaction. The frontend may predict reversible presentation state only. It must reconcile lifecycle, chat, deletion, and permissions from the response or stream.

For junior developers: do not infer a missing transition. Example: disabling a button is helpful UX, but it does not prevent two tabs from submitting the same operation. The database constraint/service transition is the correctness boundary.

## Global invariants

1. A member sees only query-eligible domains, their own conversations, and evidence authorized for the selected turn.
2. An administrator gains operational capabilities, not access to members' private conversation content unless a separately approved contract allows it.
3. A request either commits its state change and required audit event together or commits neither.
4. Duplicate requests with the same idempotency key and fingerprint reuse the existing result; the same key with different input returns `409 idempotency_conflict`.
5. Stale operation completions cannot overwrite a newer generation.
6. Navigation state may contain safe opaque IDs and viewer coordinates, never storage paths, provider URLs, credentials, or private block identifiers.
7. A stale UI receives a safe conflict/current-state response and refreshes; it never forces its old state onto the server.

## Member role-play

### M-01 Login and session replacement

- **Given:** valid enabled member credentials and no valid session.
- **When:** the member submits login with valid Origin and CSRF bootstrap data.
- **Then:** FastAPI rotates any prior session, sets the opaque HttpOnly cookie, and returns the safe current-user projection; the UI enters `/chat`.
- **Race/failure:** two successful logins create independently revocable sessions unless the configured concurrent-session limit evicts the oldest. Invalid credentials reveal neither username existence nor disabled status.

### M-02 Domain selection

- **Given:** domains A and B are query-eligible for the member.
- **When:** the member selects A.
- **Then:** the composer displays A as the effective domain for the next turn; no conversation or server record changes until submit.
- **Race/failure:** if A stops before submit, the server rejects the turn with `domain_not_query_eligible`; the UI preserves the draft, clears or marks the stale selection, refreshes domains, and does not silently query B or use direct chat.

### M-03 Grounded question and streamed answer

- **Given:** the member owns conversation C and selects eligible domain A.
- **When:** they submit question Q with client request ID R.
- **Then:** one `domain_rag` turn is created for C/A/R; authorized evidence is persisted before or atomically with terminal completion; ordered status/evidence/answer events render through the canonical reducer.
- **Race/failure:** closing the socket does not cancel or complete the turn by assumption. Reopen resumes after the last applied sequence. No evidence means a grounded refusal, not an answer from general knowledge.

### M-04 Figure evidence deep-link

- **Given:** selected turn T contains authorized figure Evidence E mapped to document D, page 18, and figure region/anchor F.
- **When:** the member clicks E.
- **Then:** the app navigates from `/chat` to `/documents?document=<safe-ref>&evidence=<safe-ref>`, opens the library viewer, expands the PDF panel, loads D through an authorized content endpoint, selects page 18, and scrolls/zooms to F. The evidence card remains identifiable for return navigation.
- **Race/failure:** if exact coordinates are unavailable, open the page and highlight the containing Source Block. If authorization or source state changed, show `Evidence no longer available` with request ID; never reveal the private object key or fall back to another document.
- **Junior example:** route state carries opaque safe refs plus `page=18`, not `C:\uploads\report.pdf` or a raw database block ID.

### M-05 Text/table evidence deep-link

- **Given:** Evidence E maps to an authorized text or table block in D.
- **When:** the member opens E.
- **Then:** `/documents` opens D at the containing page/section, highlights the safe excerpt, and exposes a return-to-turn action.
- **Race/failure:** changed viewer layout may alter pixels, so persistence uses semantic anchors (`page`, block-safe-ref, optional region), not scroll offsets alone.

### M-06 Evidence selection is turn-scoped

- **Given:** conversation C has turns T1 and T2 with different evidence.
- **When:** the member selects T1.
- **Then:** the Evidence Panel contains only T1 evidence; selecting T2 atomically replaces the panel projection.
- **Race/failure:** a slow T1 response arriving after T2 selection is discarded by request/selection generation and cannot overwrite T2.

### M-07 Direct chat without a domain

- **Given:** no domain is selected.
- **When:** the member asks a narrow general question allowed by the intent gate.
- **Then:** the server creates a `direct_llm` turn with no domain and no evidence.
- **Race/failure:** a domain-seeking question returns `domain_required`; the UI preserves the draft and prompts for a domain. It does not choose a domain automatically.

### M-08 Conversation ownership and deletion

- **Given:** member U owns conversation C.
- **When:** U renames or deletes C.
- **Then:** rename updates C once; delete removes C from U's list and invalidates open views after server confirmation.
- **Race/failure:** another member receives indistinguishable not-found/denied behavior. Two delete requests converge on deleted/not-found without recreating data. A turn submission racing deletion must serialize to either a committed turn in a live conversation or a rejected submission, never an orphan.

### M-09 Composer references

- **Given:** the member discovers authorized source/evidence/template references.
- **When:** they attach ordered refs and submit.
- **Then:** the server consumes valid opaque tokens, persists safe accepted-ref metadata and private linkage, and fingerprints the effective ordered set.
- **Race/failure:** expired, reused one-use, duplicated, incompatible-domain, or newly unauthorized refs reject the turn before provider work. The UI identifies invalid chips without exposing target IDs.

### M-10 Concurrent tabs submit the same draft

- **Given:** two tabs show conversation C and share client request ID R for the same draft.
- **When:** both submit identical input.
- **Then:** one turn is created; both attach to or replay that turn.
- **Race/failure:** if one tab changes the message/domain/refs but reuses R, that request receives `409 idempotency_conflict`; no second provider call occurs.

### M-11 Source deletion redacts an open answer

- **Given:** the member is viewing completed turn T citing source S while an admin deletes S.
- **When:** deletion reaches its redaction transaction.
- **Then:** T becomes `redacted`; assistant answer and public citations disappear on refresh/replay and the UI shows a redaction state while preserving the user question.
- **Race/failure:** an already open Evidence/PDF panel loses access on its next authorized fetch/event and closes with a safe message. Browser cache must not continue serving protected source content.

## Administrator role-play

### A-01 Provider credential update

- **Given:** an administrator opens provider P settings.
- **When:** they submit replacement credentials.
- **Then:** the backend encrypts and replaces the credential, returns presence/update metadata only, and writes the audit event atomically.
- **Race/failure:** concurrent updates use a version/ETag; the loser receives `409 stale_revision`. The UI never rehydrates or displays the stored secret.

### A-02 Model profile and immutable embedding selection

- **Given:** embedding profile E is used by domain A.
- **When:** an admin attempts to change E's vector dimensions or replace A's profile.
- **Then:** the server rejects the mutation because the domain embedding contract is frozen.
- **Race/failure:** creating a new profile is allowed; migrating an existing domain requires a separately approved re-index workflow, never an in-place edit.

### A-03 Create and start a domain

- **Given:** a valid immutable embedding profile exists.
- **When:** an admin creates domain A and then starts it.
- **Then:** create commits A as `stopped`; start commits one queued/running operation with generation G; worker success changes A to `running` only if lease and G remain current.
- **Race/failure:** simultaneous start requests converge on the same active operation or return `operation_conflict`. A stale worker for G cannot overwrite stop/delete generation G+1.

### A-04 Stop domain during active member query

- **Given:** member turn T is retrieving from running domain A.
- **When:** an admin stops A.
- **Then:** new queries are rejected immediately after the stop fence commits. T follows the documented policy: finish from already authorized captured evidence or terminate with `domain_became_unavailable`; it may not perform new retrieval after the fence.
- **Race/failure:** the result records which policy occurred and remains replayable. It never silently reroutes to another domain or direct LLM.

### A-05 Concurrent domain controls

- **Given:** admins X and Y view running A.
- **When:** X requests stop while Y requests delete.
- **Then:** service locking chooses one legal transition. Delete may supersede/cancel stop by incrementing generation; otherwise one request returns `operation_conflict` with current state.
- **Race/failure:** button state in either browser is irrelevant to correctness. Exactly one current generation controls workers.

### A-06 Upload and deduplicate a document

- **Given:** domain A exists and source bytes hash to H.
- **When:** two admins concurrently upload identical bytes under different filenames.
- **Then:** server-computed `(domain_id, H)` uniqueness creates one source and one preparation workflow; both callers receive the canonical safe source result or one receives a deterministic duplicate response.
- **Race/failure:** interrupted upload commits neither a usable source nor a worker operation. A client-provided digest never overrides the server-computed digest.

### A-07 Preparation retry/cancel

- **Given:** preparation operation P failed or is running.
- **When:** an admin retries or cancels P.
- **Then:** retry creates/advances one generation with frozen parser kind; cancel marks the current generation cancelled and prevents its completion from publishing blocks.
- **Race/failure:** retry racing a late success accepts only the generation that wins the guarded transition. Canonical blocks are replaced atomically, never partially appended.

### A-08 Indexing and query eligibility

- **Given:** prepared source S belongs to running A.
- **When:** an admin requests indexing.
- **Then:** one idempotent handoff is submitted; S becomes query-eligible only after readiness and provenance mapping are verified.
- **Race/failure:** provider timeout leaves a retryable operation with safe error. Repeated submit uses the stable operation/content key. A `processing` source is not exposed as ready.

### A-09 Delete source with downstream effects

- **Given:** S is indexed and cited by turns and governed composer references.
- **When:** an admin confirms delete.
- **Then:** one transaction fences S from retrieval, creates the delete operation, redacts affected turns, invalidates governed refs, and records audit intent; remote/object cleanup proceeds idempotently before final row removal.
- **Race/failure:** cleanup failure leaves visible admin operation state and S unavailable for queries. Retry continues cleanup; it must not undo redaction or restore eligibility.

### A-10 Delete domain

- **Given:** A contains sources, operations, and cited turns.
- **When:** an admin deletes A.
- **Then:** A immediately enters `deleting`, disappears from member selection, blocks new work, fences workers by generation, redacts dependent turns, invalidates governed refs, and performs idempotent runtime/object cleanup.
- **Race/failure:** concurrent uploads, starts, indexing, and questions after the fence are rejected. Failed cleanup remains recoverable from the admin operation view; no partial state is presented as deleted.

### A-11 Runtime settings changed during work

- **Given:** operation P captured parser/model/runtime configuration version V.
- **When:** an admin changes the active default to V+1 while P runs.
- **Then:** P completes using its frozen execution inputs; new operations use V+1.
- **Race/failure:** credentials may resolve at execution according to the adapter contract, but parser kind, embedding dimensions, content hash, and operation generation cannot drift mid-operation.

## Multi-user shared-state role-play

### C-01 Many members query one domain

- **Given:** A is eligible and N authorized members submit independent turns.
- **When:** requests execute concurrently.
- **Then:** each turn retains its owner, conversation, idempotency key, trace, evidence order, and stream sequence. Retrieval may share infrastructure but never mixes request context or evidence projections.
- **Race/failure:** capacity limits return `429`/`503` with retry guidance before unbounded queue growth. One cancelled stream does not cancel another user's retrieval/model call.

### C-02 Admin mutation versus member read

- **Given:** a member lists sources while an admin changes source state.
- **When:** reads and mutation overlap.
- **Then:** each response represents a valid committed snapshot. Subsequent actions revalidate current state in the mutation transaction.
- **Race/failure:** the UI must tolerate an item disappearing or becoming unavailable between list and open; it shows a safe state change, not a generic crash.

### C-03 Simultaneous evidence navigation

- **Given:** two members open the same authorized source from different turns.
- **When:** both navigate to different evidence anchors.
- **Then:** viewer selection is per browser/session; neither writes shared source state or changes the other's location.
- **Race/failure:** shared caches key authorization-sensitive responses correctly and cannot return one member's evidence projection to another.

### C-04 Concurrent conversation isolation

- **Given:** users U1 and U2 each have conversation IDs unknown to the other.
- **When:** both stream, rename, delete, or resume conversations concurrently.
- **Then:** ownership filters apply to every read/mutation/stream query; database IDs alone never grant access.
- **Race/failure:** timing, error body, and status do not disclose whether another user's conversation exists.

### C-05 Admin role revoked during a session

- **Given:** X is logged in as admin and another authorized process downgrades/disables X.
- **When:** X submits a protected mutation afterward.
- **Then:** current user/role/session state is checked server-side and the mutation is denied; the UI refreshes identity/navigation.
- **Race/failure:** an operation already committed remains valid and audited under the role at request time. Queued work does not inherit broader authority than its recorded request.

## UI interruption rules

- Route changes do not cancel server work unless the user explicitly invokes a supported cancel action.
- Draft text is preserved after recoverable conflict, domain unavailability, CSRF refresh, rate limit, or network failure.
- Destructive confirmation names the affected object and downstream behavior; closing the dialog commits nothing.
- A success toast appears only after authoritative acceptance, not button click.
- Stream status distinguishes reconnecting, completed, failed, cancelled, and redacted.
- Browser Back restores safe selection/presentation state but revalidates protected content.
- Keyboard focus follows navigation: opening evidence focuses the viewer heading/anchor; closing the panel returns focus to the originating evidence card.

## Required test mapping

Each case must map to at least one test identifier using its case ID:

- service/state-machine unit tests for legal and illegal transitions;
- repository tests for uniqueness, locking, generation fences, and transaction rollback;
- contract tests for status/error/SSE projections;
- browser tests for route, focus, panel, stale-response, and draft-preservation behavior;
- concurrency tests using real PostgreSQL transactions for every `Race/failure` clause involving shared state.

Example names: `test_M04_figure_evidence_opens_scoped_pdf`, `test_A05_delete_supersedes_stale_stop_generation`, and `test_C01_concurrent_turns_never_mix_evidence`.
