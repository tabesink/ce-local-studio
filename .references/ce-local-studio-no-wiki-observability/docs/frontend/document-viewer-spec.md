# Document Library and Viewer Specification

Status: normative implementation contract for /documents and evidence deep links.

## Product boundary

The viewer renders an authorized public document projection. It never receives an object-store key, filesystem path, presigned infrastructure URL, parser payload, private Source Block ID, or LightRAG identifier. All content and anchors are resolved by FastAPI through the same-origin BFF.

Members may open documents authorized by the member-read contract or by turn evidence. Administrators additionally manage upload, preparation, indexing, retry, cancel, and deletion. UI role checks hide controls; service authorization remains decisive.

## Desktop layout

    +--------------------------------+--------------------------------+
    | Library                         | Viewer                         |
    | filters + dense source table    | toolbar + PDF/content canvas   |
    | independent vertical scroll     | independent vertical scroll    |
    +--------------------------------+--------------------------------+

- With no document selected, Library uses the full work surface.
- With selection, split defaults to 50/50; each pane has a 420 px useful minimum.
- The separator is pointer and keyboard resizable and persists the ratio per browser.
- The selected table row remains visible and semantically selected.
- Closing Viewer keeps domain/filter/sort and removes document anchor URL state.

Below 1024 px, Library and Viewer become a list/detail flow. Viewer has Back to library. Evidence deep links enter Viewer directly and Back returns to the originating turn when a validated return target exists.

## Library

Toolbar:

- authorized Knowledge Domain selector;
- filename search;
- state filters;
- sort;
- admin Upload;
- Refresh.

Table columns:

| Column | Rule |
| --- | --- |
| Filename | sanitized display name, file-kind icon |
| Preparation | typed status pill |
| Index | typed status pill |
| Size | formatted safe bytes |
| Blocks/assets | safe counts when authorized |
| Updated | locale display with machine-readable datetime |
| Actions | role/state-derived menu, always keyboard/touch accessible |

Initial loading uses row skeletons. Refresh preserves rows. Empty state distinguishes no sources from no filter matches. Pagination/sort/filter are server-backed when the corpus exceeds one page.

## Viewer content contract

Frontend consumes:

- safe document ref and display metadata;
- same-origin content response with an allowlisted media type;
- page count and optional safe outline;
- optional evidence anchor resolved for the current user;
- content revision/version for stale-anchor detection.

Content responses use private/no-store semantics unless a separately approved user-partitioned cache exists. The BFF forwards Range requests and strips infrastructure headers. The browser must not fetch object storage directly.

PDF is rendered with a pinned PDF.js worker served by the application. Disable embedded JavaScript, launch actions, external file references, automatic form submission, and arbitrary external link navigation. External links require an explicit safe-link interstitial.

## Viewer state machine

| State | Rendering |
| --- | --- |
| resolving | stable viewer skeleton and requested safe label |
| loading-content | toolbar disabled selectively; page skeleton |
| ready | document, outline, controls, optional focus anchor |
| anchor-pending | content visible; Locating evidence status |
| anchor-focused | target page and highlight visible |
| stale-anchor | page fallback plus safe explanation |
| unavailable | no content; Evidence no longer available; request ID |
| forbidden | same unavailable shape; no existence disclosure |
| failed | safe error, retry content request |

A later request may update the viewer only if its document/evidence/session generation still matches. Closing or selecting another document aborts outstanding fetch, render, text-layer, and thumbnail work.

## Anchor model

Persist semantic anchors, not viewport scroll offsets.

    ViewerAnchor {
      pageNumber: positive integer
      region?: { x: 0..1, y: 0..1, width: 0..1, height: 0..1 }
      sectionLabel?: safe string, max 160 characters
      fallback: "region" | "section" | "page"
    }

Region coordinates are normalized to the unrotated PDF crop box with origin at top-left. The frontend transforms them for rotation, zoom, and device scale. Clamp every value and reject a region outside the page.

The document/evidence response carries document identity and preview version separately. Do not add private block refs, quotes, content revisions, or viewport offsets to `ViewerAnchor`.

Resolution order:

1. verify document and evidence authorization;
2. load the authorized governed preview/version declared by the document response;
3. open `pageNumber`;
4. locate exact region;
5. otherwise locate `sectionLabel` on that page;
6. otherwise open the page according to `fallback: "page"` and show Exact location unavailable;
7. never search another document as a fallback.

## Evidence-kind behavior

| Kind | Required focus |
| --- | --- |
| figure | page, figure bounding region, caption when available |
| table | page, table region, accessible table summary when available |
| text | page and text-layer range or containing block |

The highlight has a visible border and translucent fill, is not color-only, and receives programmatic focus after the page settles. A short status announces Figure on page 18 focused. Do not continuously re-scroll after the user moves away.

## Viewer toolbar

Required controls:

- page previous/current/next;
- zoom out/reset/in;
- fit width and fit page;
- rotate view;
- outline toggle when available;
- evidence focus/reset;
- download only when explicitly authorized by the response;
- close/back.

Controls have labels and shortcuts. Page input validates 1..pageCount. Zoom clamps to 50-400%. Ctrl/Cmd+plus/minus follows browser conventions only when focus is inside the viewer and does not prevent browser zoom globally.

## Admin operations panel

Show safe metadata, preparation/index state, operation attempts, timestamps, and safe failure message. Buttons derive from the server-provided allowed-actions projection:

- retry/cancel preparation;
- retry/cancel indexing;
- delete source.

Do not render every button disabled for every state. Delete dialog names the source and explains that retrieval is fenced before artifacts are removed and affected answers may be redacted. Success closes unavailable content only after server confirmation. Conflict refreshes current state in place.

## Deep-link transaction

For M-04:

1. evidence card navigates to /documents with safe document/evidence refs and page hint;
2. route renders shell and viewer skeleton immediately;
3. server reauthorizes both refs and returns canonical anchor;
4. content loads and page 18 renders;
5. viewer transforms and focuses the figure region;
6. Return to answer restores /chat conversation/turn/evidence selection.

The page query is a hint; the authorized anchor response wins. If evidence was deleted between steps 1 and 3, show unavailable and do not load a document based only on the document query.

## Performance and accessibility

- Render visible page plus one page ahead/behind; cancel distant render tasks.
- Virtualize thumbnails; never instantiate every canvas for a large PDF.
- Cap decoded image dimensions and memory; show a safe too-large state.
- The PDF text layer remains selectable and exposed to assistive technology.
- Outline, thumbnails, page canvas, and toolbar have ordered landmarks.
- At 200% and 400% zoom, including approximately 320 CSS px reflow, controls wrap or substitute without covering the page.
- Reduced motion removes smooth auto-scroll but preserves focus.

## Required proofs

Hooks: document-library, document-row-{safe-ref}, document-viewer, viewer-toolbar, pdf-page-{number}, evidence-highlight, viewer-unavailable, source-operations.

Tests cover figure/text/table anchors, rotations and zoom, semantic fallback, stale revision, range requests, unauthorized refs, source deletion while open, rapid document switching, browser Back/Forward, member/admin controls, narrow list/detail, keyboard resize, 200%/400% zoom and 320 CSS px reflow, malicious PDF features, and absence of private identifiers in URL/DOM/network responses.
