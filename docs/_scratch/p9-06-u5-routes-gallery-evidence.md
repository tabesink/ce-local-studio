# P9-06 U5 — Route-feature parity evidence

Date: 2026-07-28  
Scope: U5 parity trios for route-feature targets. No production migration in this slice.

## Summary

| targetId | Physical owner | Import path (parity tests) | Layer | catalogState |
| --- | --- | --- | --- | --- |
| `document-library` | `app/client/src/features/documents/DocumentsPage.tsx` | `@/features/documents/DocumentsPage` | feature | FACTORY_READY |
| `document-viewer` | `app/client/src/features/documents/PdfPreview.tsx` | `@/features/documents/PdfPreview` | feature | FACTORY_READY |
| `settings-nav` | `SettingsPanel` → `SettingsLayout` / `SectionNav` | `@/_shared/ui` (`SettingsLayout`) | feature | FACTORY_READY |
| `settings-group` | `SettingsPanel` → `SettingsGroup` + `SettingsRow` | `@/_shared/ui` + `@/features/settings-panel/SettingsRow` | feature | FACTORY_READY |
| `login` | `app/client/src/features/auth/LoginPage.tsx` | `@/features/auth/LoginPage` | feature | FACTORY_READY |
| `graph-unavailable` | `app/client/src/features/graph/GraphPage.tsx` | `@/features/graph/GraphPage` | feature | FACTORY_READY |

## Composition notes

- **document-library** captures the library column only (PageHeader, domain select, filter, dense table). Preview panel and PdfPreview chrome are owned by **document-viewer**.
- **document-viewer** tests PdfPreview toolbar + canvas region with mocked `pdfjs-dist`; HTML fixtures use a synthetic canvas placeholder — no real PDF bytes or object-store payloads.
- **settings-nav** exercises `SettingsLayout` section navigation (member General-only vs administrator four-section list). Domain accordion disclosure is **not** duplicated — see **domains-accordion**.
- **settings-group** covers grouped section chrome (`SettingsGroup` title/description/bordered body) with `SettingsRow` children. Row shell parity remains in **settings-row**; accordion rows remain in **domains-accordion**.
- **login** is a standalone centered credential card with no app rail.
- **graph-unavailable** is the deliberate DRIFT-04 unavailable surface only — zero product-data requests, no canvas, no LightRAG placeholders.

## Related parity targets (not duplicated)

| targetId | Why referenced |
| --- | --- |
| `domains-accordion` | Settings Knowledge Domains disclosure rows |
| `settings-row` | Individual settings row shell |
| `pane-header` | Shared PageHeader used inside library/graph/settings surfaces |

## Parity trio paths

| targetId | manifest | fixture | react test |
| --- | --- | --- | --- |
| `document-library` | `app/client/tests/parity/manifests/document-library.json` | `app/client/tests/parity/fixtures/document-library.html` | `app/client/tests/parity/react/document-library.test.tsx` |
| `document-viewer` | `app/client/tests/parity/manifests/document-viewer.json` | `app/client/tests/parity/fixtures/document-viewer.html` | `app/client/tests/parity/react/document-viewer.test.tsx` |
| `settings-nav` | `app/client/tests/parity/manifests/settings-nav.json` | `app/client/tests/parity/fixtures/settings-nav.html` | `app/client/tests/parity/react/settings-nav.test.tsx` |
| `settings-group` | `app/client/tests/parity/manifests/settings-group.json` | `app/client/tests/parity/fixtures/settings-group.html` | `app/client/tests/parity/react/settings-group.test.tsx` |
| `login` | `app/client/tests/parity/manifests/login.json` | `app/client/tests/parity/fixtures/login.html` | `app/client/tests/parity/react/login.test.tsx` |
| `graph-unavailable` | `app/client/tests/parity/manifests/graph-unavailable.json` | `app/client/tests/parity/fixtures/graph-unavailable.html` | `app/client/tests/parity/react/graph-unavailable.test.tsx` |

## React stubbing approach

| target | stubs |
| --- | --- |
| `document-library` | `next/navigation`, `useAuthStore` member user, `listMemberDomains`, `listDocuments` / `listAdminSources` mocked — no network |
| `document-viewer` | `pdfjs-dist` mocked; canvas `getContext` stubbed for jsdom |
| `settings-nav` | No network; synthetic section defs passed to real `SettingsLayout` |
| `settings-group` | No network; real `SettingsGroup` + `SettingsRow` with synthetic labels |
| `login` | `next/navigation` (`replace`), `useAuthStore.login` mock — no network |
| `graph-unavailable` | No stubs; static component only |

## Blockers / deferrals

- **document-viewer** does not prove real pdf.js rendering or governed byte-range fetch — chrome and navigation only.
- **document-library** admin upload/ops rows deferred to settings/admin slices; member read-only marker asserted.
- **settings-nav** URL `?section=` routing is owned by `SettingsPanel` integration tests elsewhere.
- `ui-parity-spec.md` catalog rows remain unchanged in this slice (per task instruction).

## Verification

Each suite was run separately from `app/client` with a 1 GiB heap and one worker so the test process releases memory between files:

```bash
NODE_OPTIONS=--max-old-space-size=1024 npx vitest run tests/parity/react/<target>.test.tsx --maxWorkers=1
```

Results: document-library 3/3, document-viewer 3/3, settings-nav 3/3,
settings-group 2/2, login 3/3, graph-unavailable 2/2. The document-library
test uses stable router, search-parameter, and user mocks; unstable identity
objects retrigger the production identity effects and are not valid test
fixtures.
