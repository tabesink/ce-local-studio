# Frontend Implementation Slices

These are coding-agent-sized vertical slices. Complete them in dependency order; do not scaffold future controls or invent missing backend fields.

## Slice completion packet

Every slice must provide:

- changed files and contract/schema version consumed;
- behavior case IDs and route/state screenshots;
- unit, accessibility, browser, and contract test IDs;
- privacy/storage/network scan result;
- explicit deferred items and stop-condition result.

A slice is incomplete when it renders fixture-only fields, relies on a mock as authority, or lacks safe loading/empty/failure/ready states.

## Ordered slices

| Slice | Inputs | Implementation and proof | Stop condition |
| --- | --- | --- | --- |
| FE-00 Repository gates | blueprint, stack, source map | Next shell; `app/features/lib/ui/styles`; import/cycle/privacy/storage/contract checks | generated client or pinned contracts unavailable |
| FE-01 Tokens/primitives | Local Studio token snapshot, accessibility contract | CE tokens; button/input/table/status/page-state/modal/drawer; Storybook or fixture gallery + axe/visual tests | license/provenance or contrast unresolved |
| FE-02 Identity shell | auth contract, M-01/C-05 | login/logout/current-user; request-scoped clients; role nav; BFCache/logout tests | cookie/CSRF/Origin behavior unproven through BFF |
| FE-03 Navigation/state | URL and ownership contracts | canonical route parsers, sidebar, responsive drawers, identity epoch, storage allowlist | a URL needs private IDs or unrestricted return URL |
| FE-04 Domain/conversation reads | domain/conversation DTOs, M-02/M-06/M-08 | eligible domain selector; list/create/load/rename/delete conversation; generation guards | ownership errors distinguish resource existence |
| FE-05 Stream runtime | SSE fixtures, M-03/M-07/M-10/C-01 | parser, reducer, cursor, POST/GET resume, reconnect UI; live/replay fixture equivalence | event schema/order/terminal snapshot not approved |
| FE-06 Chat workbench | FE-04/05, component/layout specs | transcript, compact composer, ordered refs, turn selection, evidence panel, draft recovery | browser introduces route/model/tool/retrieval authority |
| FE-07 Evidence/Library | safe content/anchor contracts, M-04/M-05/M-11 | single Library route, source table, inline PDF viewer/mobile drawer, semantic anchors, return focus | content endpoint exposes path/URL or lacks reauthorization |
| FE-08 Admin source/domain operations | operation DTOs, A-03..A-10 | upload, prepare/index controls, start/stop/delete, operation conflict/recovery states | mutation lacks idempotency/version/current-state response |
| FE-09 Graph | approved graph DTO, route spec | domain-scoped canvas, controls, node detail, searchable accessible alternative | graph contract would expose runtime/private block IDs |
| FE-10 Settings | runtime-setting DTOs, A-01/A-02/A-11 | member/admin sections, credential replacement, safe conflicts and frozen-operation inputs | stored secret/provider payload appears in DTO |
| FE-11 Hardening/release | all frontend specs | responsive/a11y/visual matrix, all E2E, deployed SSE, cache isolation, load/failure evidence | any case lacks mapped proof or real-ingress verification |

## Per-slice file rule

Use this shape unless an existing approved package differs:

```text
src/app/<route>/page.tsx             thin composition only
src/features/<capability>/api.ts     typed capability adapter
src/features/<capability>/store.ts   interaction projection, if needed
src/features/<capability>/selectors.ts
src/features/<capability>/ui/*.tsx
src/features/<capability>/*.test.ts
```

Shared code moves to `lib`/`ui` only after two real feature consumers exist. No `components` catch-all and no feature importing `app`.

## Agent execution recipe

1. Read the named input contracts and inspect exact reference anchors in `source-adaptation-map.md`.
2. Write failing boundary/state tests for the listed cases.
3. Generate/update API types; do not hand-copy DTOs.
4. Implement one end-to-end user intent with all four surface states.
5. Verify keyboard/focus, mobile/desktop geometry, URL canonicalization, and authoritative reconciliation.
6. Run the slice tests plus root structural/type/build gates.
7. Produce the completion packet; stop without beginning the next slice.

## Integration checkpoints

| Checkpoint | Required result |
| --- | --- |
| after FE-03 | member/admin can authenticate and navigate without protected cache/storage leakage |
| after FE-06 | one durable direct and grounded turn streams, reconnects, replays, and scopes evidence |
| after FE-08 | admin can create/run a domain, upload/prepare/index a source, and observe recoverable operations |
| after FE-11 | every M/A/C case maps to browser plus lower-boundary proof and release artifacts |

## Global stop conditions

Stop the current slice and record the missing authority when:

- a browser-visible field/event/error is absent from OpenAPI/SSE contracts;
- a task needs credentials, infrastructure addresses, paths, private IDs, or direct provider/storage/runtime access;
- a delete/redaction/role change cannot be reconciled from server truth;
- a mock is the only proof of authorization, concurrency, streaming, or recovery;
- parity conflicts with accessibility or security and no approved divergence exists.

Do not fill the gap with placeholder working controls. Render an explicitly unavailable state only when the product contract permits the surface to exist before its backend capability.
