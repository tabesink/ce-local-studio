# P9-06 U4 — Chat feature composite parity evidence

Date: 2026-07-28  
Scope: U4 parity trios for `conversation-rail`, `transcript`, `composer`, `evidence-inspector`, and optional `chat-workbench`. No production extraction in this slice.

## Summary

| targetId | Physical owner | Import path (parity tests) | Layer | catalogState |
| --- | --- | --- | --- | --- |
| `conversation-rail` | `ChatShell.tsx` pane header + `ConversationPicker` | `@/features/chat-shell/ChatShell` (stubbed hook) | feature | FACTORY_READY |
| `transcript` | `ChatShell.tsx` timeline + `TimelineMessage` | `@/features/chat-shell/ChatShell` (stubbed hook) | feature | FACTORY_READY |
| `composer` | `ChatShell.tsx` lifted composer form | `@/features/chat-shell/ChatShell` (stubbed hook) | feature | FACTORY_READY |
| `evidence-inspector` | `EvidencePanel.tsx` | `@/features/chat-shell/EvidencePanel` | feature | FACTORY_READY |
| `chat-workbench` | `ChatShell.tsx` + `EvidencePanel.tsx` composition | `@/features/chat-shell/ChatShell` (stubbed hook) | feature | FACTORY_READY |

## Composition notes

- **ConversationRail** is the chat pane header region (title, stream pill, conversation picker, new conversation, inspector toggle). It is not the app discovery `NavigationRail`.
- **Transcript**, **Composer**, and the header share `ChatShell.tsx`; parity tests stub `useChatShell` rather than extracting presentational subcomponents.
- **EvidenceInspector** is the exported `EvidencePanel` turn-scoped aside/drawer with Evidence | Refs | Source tabs.
- **ChatWorkbench** is the combined main column + optional inspector geometry target for HTML steering.
- References picker remains gated unavailable (`data-testid="ref-picker"`); no P11-04 attach/suggest chips were added.

## Parity trio paths

| targetId | manifest | fixture | react test |
| --- | --- | --- | --- |
| `conversation-rail` | `app/client/tests/parity/manifests/conversation-rail.json` | `app/client/tests/parity/fixtures/conversation-rail.html` | `app/client/tests/parity/react/conversation-rail.test.tsx` |
| `transcript` | `app/client/tests/parity/manifests/transcript.json` | `app/client/tests/parity/fixtures/transcript.html` | `app/client/tests/parity/react/transcript.test.tsx` |
| `composer` | `app/client/tests/parity/manifests/composer.json` | `app/client/tests/parity/fixtures/composer.html` | `app/client/tests/parity/react/composer.test.tsx` |
| `evidence-inspector` | `app/client/tests/parity/manifests/evidence-inspector.json` | `app/client/tests/parity/fixtures/evidence-inspector.html` | `app/client/tests/parity/react/evidence-inspector.test.tsx` |
| `chat-workbench` | `app/client/tests/parity/manifests/chat-workbench.json` | `app/client/tests/parity/fixtures/chat-workbench.html` | `app/client/tests/parity/react/chat-workbench.test.tsx` |

## React stubbing approach

| target | stubs |
| --- | --- |
| ChatShell regions | Shared `tests/parity/react/chat-shell-stubs.ts` hoisted `mockChatShell`; `vi.mock("@/features/chat-shell/use-chat-shell")`; `next/navigation` `useSearchParams` + `useRouter`; synthetic conversations/messages/evidence only |
| `evidence-inspector` | `next/navigation` `useRouter`; direct `EvidencePanel` render; `window.matchMedia` for desktop vs drawer paths |
| `chat-workbench` | Same ChatShell stub with `panelOpen` + `panelEvidence` to assert combined composition |

## Blockers / deferrals

- Live subcomponents (`ConversationPicker`, `TimelineMessage`, `DomainPicker`) remain private to `ChatShell.tsx`; extraction deferred unless a future slice needs reuse.
- P9-02 `chat-inspector.test.tsx` remains the deeper Library navigation proof; U4 parity tests focus on catalog geometry and R10 hooks.
- `ui-parity-spec.md` catalog rows remain `NOT_STARTED` until U6 index/enforcement closure (per task instruction: do not edit spec in this slice).

## Verification

Each suite was run separately from `app/client` to keep memory bounded:

```bash
NODE_OPTIONS=--max-old-space-size=1024 npx vitest run tests/parity/react/<target>.test.tsx --maxWorkers=1
```

Results: conversation-rail 6/6, transcript 6/6, composer 6/6,
evidence-inspector 6/6, chat-workbench 4/4.
