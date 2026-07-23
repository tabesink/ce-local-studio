# Knowledge Graphs — anatomy

Target grammar (Controllers-style). ASCII only — adapt density from `environment-controls`, not from ad-hoc live markup.

## Settings content column

```
┌ SettingsLayout content ──────────────────────────────────────────┐
│ Section: Knowledge Graphs                                        │
│                                                                  │
│ ┌ SettingsGroup "Knowledge Graphs" ────────────────────────────┐ │
│ │ Lifecycle on backend. No Docker / port / URL details.        │ │
│ ├──────────────────────────────────────────────────────────────┤ │
│ │ ▸ Fatigue Manuals              [running]   [Stop]            │ │
│ │   fatigue                                                    │ │
│ ├──────────────────────────────────────────────────────────────┤ │
│ │ ▾ Homelab                      [stopped]   [Start]           │ │
│ │   homelab                                                    │ │
│ │   ┌ expanded (safe) ───────────────────────────────────────┐ │ │
│ │   │ Embedding: <profile label> · locked                    │ │ │
│ │   │ Storage                                 [near limit?]  │ │ │
│ │   │   28 MB of 5 GB                                        │ │ │
│ │   │   [████████░░░░] one total ProgressBar                 │ │ │
│ │   │                                        [ Delete ]      │ │ │
│ │   └────────────────────────────────────────────────────────┘ │ │
│ ├──────────────────────────────────────────────────────────────┤ │
│ │ (empty) No Knowledge Graphs configured.                      │ │
│ └──────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ ┌ SettingsGroup "New Knowledge Graph" (or Deploy footer) ──────┐ │
│ │ [name____] [id____] [embedding ▾]              [Deploy]      │ │
│ └──────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ SettingsNotice (danger/good) — safe copy only                    │
└──────────────────────────────────────────────────────────────────┘
```

## Collapsed row (target)

```
[chevron]  Display name                 [StatusPill]  [Start|Stop XOR]
           mono domain id
```

- One expanded row at a time (or collapse current).
- Storage bars are **not** drawn while collapsed.

## Expanded body (target)

```
Embedding (read-only / locked label)
Storage header + optional warning pill
  total / limit mono summary from storageSummary
  one ProgressBar(totalPercent)  — plan 002 compact surface
quiet Delete (confirm via UiModal)
```

Closed component breakdown rows (`source_storage` / `graph_index` / `database_metadata`) remain on the admin DTO for other consumers but are **out of v1 Settings chrome** (plan 002 omits them here).

## What is not drawn

- Host ports, runtime URLs, container ids, compose targets
- Storage filesystem paths
- Radio “active controller”
- Nested storage-breakdown chevrons / component bar stacks on this compact Settings surface
