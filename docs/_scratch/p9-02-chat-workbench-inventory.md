# P9-02 Chat Workbench Canonical Stream Reducer Inventory

Date: 2026-07-27

Owner: P9-02

Status: DONE — inventory complete before behavior changes

Requirements and decisions: R1–R17; KTD1–KTD9; M-02/M-03/M-06–M-08/M-10/M-11;
C-03/C-04; FR-06/FR-10; DRIFT-01/02/03/06/24;
`docs/plans/2026-07-27-009-feat-chat-workbench-reducer-plan.md`.

## Scope

- Inventory retain/modify/defer for chat-shell modules, stream helpers,
  generated OpenAPI/SSE types, BFF SSE proxy, fixture harness coverage,
  structural/E2E tests, and DRIFT consumer residuals before U2–U6 edits.
- Pin KTD1 (gate picker → P11), KTD2 (local proof altitude), KTD3 (opaque
  Library hrefs; disable when unavailable), KTD4 (`src/lib/stream/`),
  KTD5 (generated types + thin adapters), KTD6 (evidence public fields),
  KTD7 (no shared `clientRequestId` storage), KTD8 (`token`/`refToken` → P11),
  KTD9 (inventory → characterize → extract).
- Record that empty-token submit remains valid without discover.
- Flag producer fixtures present for AE1–AE3 (none missing).

## Disposition register

| Surface / call site | Prior evidence | Disposition | P9-02 target |
| --- | --- | --- | --- |
| `features/chat-shell/api.ts` handwritten `ChatTurn` / thin evidence | Lifted vs `TurnDto` / `EvidenceItemDto` | modify | Adopt generated component types; expand evidence public fields |
| `ComposerRef.refToken` + `discoverComposerRefs` | Runtime discover returns `refToken`; catalog `ComposerRefDto.token` | defer discover; gate calls | Remove discover call sites (KTD1/KTD8); P11 repairs field name |
| `features/chat-shell/stream-protocol.ts` | Dual-cursor consumer; fixture subset green/red mix | modify → move | Extract to `src/lib/stream/` |
| `lib/api/sse-parser.ts` | Single-line `data:`; 5 stream-protocol subtests red | modify → move | Same characterization unit as consumer |
| `features/chat-shell/stream-reconnect.ts` | `maxAttempts ?? 4`, backoff cap `4000` | modify → move | Contract: 5 attempts, `min(8000, …)` |
| `use-chat-shell.ts` `applyTurnStreamEvent` | Parallel reducer in hook (DRIFT-03) | replace | Pure reducer in `lib/stream/`; hook projects |
| Draft clear on submit | Clears input/refs before `turn.accepted` | modify | Submitted snapshot cleared only after acceptance |
| `clientRequestId` | New ID every submit | modify | One ID per effective draft; reuse on uncertain POST |
| `410 cursor_expired` / `terminalSnapshot` | Generated types exist; no client branch | add | Replace projection; else `getConversation`; else unavailable |
| `EvidencePanel.tsx` | Evidence-only; pointer-oriented; forbids Library nav | modify | Evidence/Refs/Source tabs; keyboard/drawer (DRIFT-02); opaque href helper |
| `@` mention picker UI | Live `mentionQuery` + discover | remove/gate | References unavailable stub + `data-testid="ref-picker"` |
| Domain selector | `<select>` + `listMemberDomains` | retain | Keep; map eligibility / `domain_required` errors |
| `ChatShell.tsx` / `@/_shared/ui` | Residual mega-kit imports | modify | Covered primitives → `@/ui` |
| `app/chat/page.tsx` | `AppShell` wraps `ChatShell` | retain | Keep ownership split |
| `NavigationSidebar` conversation list | Uses `listConversations` | retain-and-adapt | Compile against thinned adapters |
| BFF `app/api/v1/[...path]/route.ts` | Catch-all streaming proxy | retain | No chat-specific protocol |
| `lib/api/generated/openapi.ts` / `sse.ts` | Types only; no endpoint fns | retain-and-consume | Thin `ceFetch` adapters |
| `tests/stream-protocol.test.mjs` | 5 of 9 fixtures; 5 subtests failing | modify | All 9 fixtures + synthetic `410` |
| `tests/chat.test.mjs` | Requires picker; forbids Library helpers; embeds reducer in hook | modify | Same-slice rewrite for KTD1/KTD3/KTD4 |
| `tests/e2e/source-ref-inspector.spec.ts` | Zero `open-in-library`; Evidence complementary | modify | Tab hooks + disabled/opaque Library behavior |
| Chat Vitest/RTL suite | Absent | add | Net-new inspector/draft component tests |
| DRIFT-01 chat half | Lifted response shapes in `api.ts` | modify → close for chat surface | Generated types for conversation/turn/evidence/SSE |
| DRIFT-02 | EvidencePanel pointer-only | modify → close | Keyboard, focus trap/return, drawer |
| DRIFT-03 / 06 / 24 consumer | Producer sealed; browser residual | modify → close consumer | Canonical reducer + fixture tests |
| P11 discover / M-09 | Backend discover exists | defer | Token discovery + `token`/`refToken` repair |
| P9-03 documents preview / M-04–M-05 E2E | Library unavailable | defer | Chat builds href; preview ownership stays P9-03 |
| P12 ingress / C-01 | Deployed drain | defer | Local fixture/component proof only |

## Module inventory

| Path | Role |
| --- | --- |
| `app/client/src/features/chat-shell/api.ts` | Thin CE HTTP/SSE adapter (lifted DTOs) |
| `app/client/src/features/chat-shell/types.ts` | Timeline / assistant block types |
| `app/client/src/features/chat-shell/use-chat-shell.ts` | Hook: draft, picker, embedded reducer |
| `app/client/src/features/chat-shell/ChatShell.tsx` | Workbench chrome |
| `app/client/src/features/chat-shell/EvidencePanel.tsx` | Evidence-only aside |
| `app/client/src/features/chat-shell/stream-protocol.ts` | Canonical consumer (feature-local) |
| `app/client/src/features/chat-shell/stream-reconnect.ts` | Resumable transport |
| `app/client/src/lib/api/sse-parser.ts` | Incremental SSE parser |
| `app/client/src/lib/api/sse.ts` | `postSse` / `getSse` |
| `app/client/src/lib/api/client.ts` / `errors.ts` | Shared fetch / ApiError |
| `app/client/src/lib/api/generated/openapi.ts` | Generated HTTP DTOs |
| `app/client/src/lib/api/generated/sse.ts` | Generated SSE event types |
| `app/client/src/app/api/v1/[...path]/route.ts` | BFF catch-all |
| `app/client/src/lib/server/bff-proxy.ts` | Streaming proxy implementation |
| `app/client/src/lib/stream/` | **Absent** — create in U3 |
| `app/client/src/app/chat/page.tsx` | Route entry |

## SSE fixture coverage matrix

| Fixture | Present | Wired in `stream-protocol.test.mjs` | U3 action |
| --- | --- | --- | --- |
| `direct-success.sse` | yes | yes (chunk sizes; some red) | keep + fix |
| `duplicate-delivery.sse` | yes | yes (red) | keep + fix |
| `sequence-gap.sse` | yes | yes | keep |
| `cancel.sse` | yes | yes (red) | keep + fix |
| `redacted.sse` | yes | yes (red) | keep + fix |
| `evidence-only.sse` | yes | **no** | wire |
| `no-grounded-context.sse` | yes | **no** | wire |
| `disconnect-resume.sse` | yes | **no** | wire |
| `terminal-replay.sse` | yes | **no** | wire |
| synthetic `410` + `terminalSnapshot` | n/a | **no** | add |

**Blocker check (AE1–AE3):** all nine producer fixtures exist under
`app/tests/fixtures/sse/`. No missing-fixture blocker before U3.

## Production call graph (target after U3–U5)

```text
/chat page → AppShell → ChatShell → use-chat-shell
  → chat-shell/api (thin, generated types)
      → ceFetch / postSse / getSse → BFF → FastAPI
      → src/lib/stream (parser + reducer + resumable transport)

NavigationSidebar → listConversations (same thin adapter)

Inspector (Evidence | Refs | Source)
  → selected turn projection only
  → documentsDeepLink helper (opaque params; disabled when unavailable)
```

## Implementation constraints pinned from plan + review

1. **KTD1:** Zero `discoverComposerRefs` call sites after U4; U5 owns unavailable stub UI.
2. **KTD2:** Do not claim P12 ingress / C-01 multi-member isolation.
3. **KTD3:** New outbound Library helper; do not overload return-to-chat `libraryDeepLink.ts`.
4. **KTD4:** One pure reduce function for live/resume/replay.
5. **KTD5:** Generated types only for chat surface — no repo-wide capabilities rewrite.
6. **KTD6:** Evidence rows must carry `documentRef`, kind, anchor for Source/Library.
7. **KTD7:** No `sessionStorage`/`localStorage` for `clientRequestId`.
8. **KTD8:** `ComposerRefDto.token` vs runtime `refToken` is P11 residual.
9. **KTD9:** U3 characterization-first against currently failing stream-protocol cases.
10. **Empty-token submit:** Valid without refs; picker gate must not break send.
11. **Inspector breakpoint:** Drawer below **1024 px**; discovery drawer below **768 px**.
12. **`npm test` short-circuit:** Node stream-protocol suite must green before composite Vitest in U6.

## Explicit deferrals

| Surface | Owner |
| --- | --- |
| Governed-ref discover / `token` vs `refToken` / M-09 | P11 |
| Documents library/preview / M-04–M-05 E2E viewer | P9-03 |
| Settings Domain accordion | P9-04 |
| Import-boundary CI pack | P9-05 |
| Deployed-ingress stream-drain / C-01 / full visual matrix | P12 |
| Evidence reattachment compose-epoch | P11-04 |
| Full `src/lib/api/capabilities/*` for non-chat | follow-up |
