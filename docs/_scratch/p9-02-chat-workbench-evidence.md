# P9-02 Chat Workbench Canonical Stream Reducer Evidence

Date: 2026-07-27

Slice: P9-02

Status: DONE (local fixture/unit/component altitude; P11 discover and P12 ingress deferred)

Plan: `docs/plans/2026-07-27-009-feat-chat-workbench-reducer-plan.md`

Inventory: `docs/_scratch/p9-02-chat-workbench-inventory.md`

Authority: closed Phase 1 chat capability manifest in `docs/prd.md` (linked, not redefined);
`docs/frontend/chat-and-evidence-workbench.md`; `docs/frontend/api-client-and-stream-runtime.md`;
`docs/contracts/sse-event-catalog.md`.

## What landed

- Generated OpenAPI/SSE component types drive thin `features/chat-shell/api.ts` adapters
  (`TurnDto`, `EvidenceItemDto`, conversation envelopes). Handwritten substitute turn/evidence
  shapes for this surface retired (DRIFT-01 chat half).
- Canonical stream runtime under `app/client/src/lib/stream/`: CRLF-safe parser, turn consumer,
  resumable transport (5 attempts / 8s backoff cap), pure `reduceTurnStreamEvent`, and
  `410 cursor_expired` / `terminalSnapshot` helpers.
- All nine producer fixtures in `app/tests/fixtures/sse/` consumed with chunked parsing;
  synthetic `410` replace coverage included.
- `use-chat-shell` consumes the canonical reducer; draft/`clientRequestId` lifecycle; mapped
  `domain_required` / eligibility / idempotency / auth / cursor-expired errors; zero
  `discoverComposerRefs` call sites (KTD1).
- Turn-scoped Evidence | Refs | Source inspector with empty states, keyboard evidence cards,
  drawer focus trap/return below 1024 px (DRIFT-02), gated References stub
  (`data-testid="ref-picker"`), and opaque Library deep-link helper
  (`documentsDeepLink.ts`) kept disabled until P9-03 preview.

## Commands

### Stream protocol + reconnect + chat structural (node:test)

```text
cd app/client
node --experimental-strip-types --test `
  tests/stream-protocol.test.mjs `
  tests/stream-reconnect.test.mjs `
  tests/chat.test.mjs
```

Result (2026-07-27): 39 tests passed / 0 failed.

### Typecheck

```text
cd app/client
npx tsc --noEmit -p tsconfig.json
```

Result: clean.

### Workbench Vitest / RTL

```text
cd app/client
npx vitest run tests/documentsDeepLink.test.ts tests/chat-inspector.test.tsx
```

Result: 2 files / 7 tests passed.

## Privacy assertions

- Opaque Library href builder only emits `document` / `evidence` / `page` query params from
  public DTO fields; unit tests forbid path/object-URL/block-id leakage.
- Open in Library control remains disabled with honest unavailable copy (P9-03 owns viewer).
- Hook does not persist prompts, answers, evidence, or composer tokens to local/session storage.
- Status line uses domain display labels, not raw domain IDs.

## Interaction-case trace (this altitude)

| Case | Evidence |
| --- | --- |
| M-02 / M-07 domain selection / `domain_required` | Hook error mapping + draft retention |
| M-03 live/resume/replay | Fixture matrix + reducer + reconnect suites |
| M-06 turn-scoped inspector | Inspector tabs + generation fence + RTL |
| M-08 rename/delete | Existing conversation adapter paths retained (CRUD via shell/rail) |
| M-10 idempotency | `clientRequestId` reuse / conflict new-ID rules in hook |
| M-11 redaction | `redacted.sse` fixture + reducer terminal |
| C-03 / C-04 | Per-tab selection; no shared storage for request IDs |

Deferred from this proof set: M-04/M-05 viewer E2E → P9-03; M-09 discover → P11;
C-01 multi-member / deployed ingress → P12.

## Residuals / non-claims

| Residual | Owner |
| --- | --- |
| Governed-ref discover UI + `ComposerRefDto.token` vs runtime `refToken` | P11 |
| Documents library/preview accepting opaque deep links | P9-03 |
| Settings Domain accordion | P9-04 |
| Import-direction / barrel CI validators | P9-05 |
| Deployed-ingress stream-drain / full visual matrix / C-01 | P12 |
| Evidence reattachment compose-epoch | P11-04 |
| Closed Phase 1 chat capability manifest completion | Not claimed — P11 discovery still open |
| Full `src/lib/api/capabilities/*` for non-chat surfaces | follow-up |

## DRIFT notes

- DRIFT-02 → DONE (keyboard/focus/drawer on Evidence inspector).
- DRIFT-03 / DRIFT-06 / DRIFT-24 consumer halves → DONE (canonical reducer + fixture tests).
- DRIFT-01 → IN_PROGRESS remains for non-chat response adoption / absent catalog ops;
  chat-shell lifted turn/evidence substitutes for this surface retired.

## Artifact revision

Branch: `feat/p9-02-chat-workbench-reducer`

Commits (slice): inventory/plan → generated DTO adapters → `src/lib/stream` + fixtures →
reducer state + Evidence/Refs/Source workbench → this evidence/tracker closure.
