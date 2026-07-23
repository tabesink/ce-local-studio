# Knowledge Graphs — behavior

## Expand / collapse

- Accordion: **one open row at a time** (toggle collapses the current id).
- Collapsed by default on load.
- Storage UI renders **only when expanded**, and only from admin `storageSummary`.
- Expand state is local UI state — not a backend “active controller” selection.

## Lifecycle

- **Deploy:** create then start as one admin gesture; refresh list afterward.
- **Start / Stop:** XOR on the row; disable conflicting controls while busy.
- **Delete:** quiet danger control + explicit `UiModal` confirm; then refresh.
- If create succeeds and start fails, keep the domain listed; do not auto-delete.

## Storage summary (safe fields)

Render only backend-owned admin `storageSummary` values (total/limit/percent/warning and closed component kinds when shown).

Do **not**:

- compute quota in the browser from paths or runtime targets
- show storage bars on the collapsed header
- display filesystem paths, ports, or runtime URLs as “storage detail”

## Forbidden UI tokens / fields

Never display (aligned with product helpers / plans):

- host ports, runtime URLs, container ids
- compose / Docker targets
- storage paths
- secrets, stack traces, raw provider payloads

## Access

- Administrator-only surface for deploy and lifecycle controls.
- Members do not get these controls here.

## Empty / error

- Empty list: safe empty notice; Deploy / create affordance still available when product allows.
- Failures: `SettingsNotice` danger with safe copy only — no infra dumps.
