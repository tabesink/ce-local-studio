# Visual Regression Plan

Visual parity means Context Engine retains Local Studio's compact dark-first grammar while using Context Engine routes, data, and security boundaries. Screenshots verify presentation; behavior tests remain authoritative for state changes.

## Tooling and determinism

- Use Playwright screenshot assertions in Chromium; run WebKit for interaction compatibility without making it the pixel baseline.
- Install and await the pinned product fonts. Disable caret, CSS animations, transitions, clocks, relative times, and random IDs in screenshot mode.
- Seed PostgreSQL and object fixtures through a versioned test-data command. Do not intercept every API into a static mock for release baselines.
- Freeze locale `en-US`, timezone `UTC`, device scale factor `1`, color scheme, and reduced-motion setting.
- Keep stable request IDs/timestamps in visual fixtures. Mask only explicitly nondeterministic infrastructure values; never mask layout or product state.

## Viewport matrix

| Name | CSS viewport | Required layout proof |
| --- | --- | --- |
| mobile | 390x844 | navigation and inspector drawers; no hidden evidence/actions |
| tablet | 768x1024 | compact shell and usable tables/forms |
| laptop | 1280x800 | canonical Local Studio parity target |
| desktop | 1440x900 | inline Library viewer and Evidence Panel |
| wide | 1920x1080 | bounded reading width; panes do not over-expand |

Also exercise 320x640 reflow, 200% and 400% browser zoom (including 1280x800 at 400%, approximately 320 CSS px), light/dark themes if both ship, and `prefers-reduced-motion`. Laptop and mobile are required on every PR; the full matrix runs before release.

## Golden personas and data

| Persona | Fixture |
| --- | --- |
| member | two eligible domains, three conversations, direct and grounded turns, figure/table/text evidence |
| administrator | domains in stopped/running/deleting states, source operations, runtime settings |
| constrained member | no domains, empty history, no admin access |

Fixtures include long titles, maximum safe excerpts, Unicode, wrapping citations, failed/reconnecting/redacted turns, stale revision, authorization loss, and a PDF figure anchor on page 18.

## Required route/state captures

| Route | States |
| --- | --- |
| `/login` | default, validation error, submitting |
| `/chat` | empty, loaded, streaming, reconnecting, evidence open, failed, redacted |
| `/documents` | empty, table, upload, inline PDF/figure anchor, unavailable, deleting |
| `/database-visualize` | deliberate unavailable state at each required viewport until graph DTO approval |
| `/settings` | member, admin, secret configured, stale revision |
| shell | expanded/collapsed sidebar, mobile drawers, forbidden, session loading |

## Baseline policy

Baselines live beside the tests and are generated from the pinned reference environment. A screenshot passes when differing pixels are at most `0.5%` with the committed Playwright threshold; text/pane clipping, missing focus, wrong state, or hidden controls fails even below that number.

Commit a machine-readable parity manifest beside the baselines. Each entry records a deterministic Local Studio source digest and exact anchor, Context Engine route/state/persona, fixture revision, viewport, zoom, theme, screenshot path, masks, threshold, and approved divergence identifier. A moving reference directory or unrecorded digest change is forbidden; a source commit may be recorded additionally only when usable Git provenance exists.

This documentation package does not claim that approved golden PNGs already exist. FE-00 must capture and review the manifest plus referenced images before any route can pass parity acceptance. Missing images, placeholder hashes, or an entry whose `approvalStatus` is not `approved` fail the visual gate.

```json
{
  "schemaVersion": "1.0",
  "sourceDigest": "sha256:<recorded-source-digest>",
  "entries": [{
    "id": "chat-member-ready-dark-1280x800",
    "sourceAnchor": "frontend/src/features/agent/ui/agent-workspace-shell.tsx",
    "route": "/chat?conversation=conv_mina_manuals&turn=turn_mina_figure&evidence=ev_mina_figure_valve&domain=domain_manuals",
    "persona": "user_member_mina",
    "fixtureRevision": "fixtures-v1",
    "viewport": {"width": 1280, "height": 800},
    "zoom": 1,
    "theme": "zai-dark",
    "expectedPath": "baselines/chromium/1280x800/chat-member-ready-dark.png",
    "masks": [],
    "maxDiffPixelRatio": 0.005,
    "approvedDivergenceId": null,
    "approvalStatus": "capture_required"
  }]
}
```

Updating a baseline requires:

1. link to the requirement or approved design change;
2. before/after images for every affected required viewport;
3. reviewer confirmation that Local Studio token/geometry parity and accessibility remain;
4. no bulk `--update-snapshots` for unrelated routes.

Do not accept platform antialias drift by widening global thresholds. Pin the container and fonts; use a narrowly documented mask only when unavoidable.

## Parity audit

For shared shell/primitives, compare against the pinned Local Studio source snapshot for sidebar width/density, header/row height, panel surfaces, typography, focus, hover, and dialog geometry. Context Engine content and route structure must not be forced into agent-specific layouts.

Each capture records viewport, persona, fixture revision, route URL, theme, source commit, and screenshot test ID. The artifact bundle includes HTML report, diffs, actuals, expected images, and console/network failures.

## Gates

- No unexpected screenshot diff, horizontal overflow, missing focus indicator, or console hydration error.
- Axe passes before capture; protected responses are `no-store` and screenshots contain only seeded synthetic data.
- Streaming screenshots are taken at reducer-controlled event barriers, never arbitrary sleeps.
- Visual proof complements E2E cases M-04/M-05, M-11, A-05, and responsive multi-user-safe states.
