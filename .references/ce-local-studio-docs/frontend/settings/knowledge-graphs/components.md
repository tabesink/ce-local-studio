# Knowledge Graphs — components

Composition uses the shared accordion/storage kit plus live `@/components/ui` primitives.
Controllers accordion row chrome remains **not exported yet** — cite `environment-controls` and adapt density locally. Do not invent an Accordion / ControllersStyle* component API.

## Composition map

| UI piece | Role | Base |
|---|---|---|
| Knowledge Graphs group | List region | `SettingsGroup` |
| Expandable domain row | Controllers-style list row (local composition) | Cite `environment-controls`; compose barrel controls below — **not in kit yet** as a single export |
| Chevron control | Expand / collapse | `IconButton` + chevron icon |
| Lifecycle status | Running / stopped / transitioning | `StatusPill` |
| Start / Stop | XOR lifecycle | `ToggleSwitch` or equivalent plan-approved control |
| Expanded embedding | Locked profile label | `Input` read-only or fact row — never a URL |
| Storage block | Expand-only usage | `ProgressBar` + `StatusPill` warning from `storageSummary` (total bar) |
| Delete | Quiet danger + confirm | Settings danger button + `UiModal` |
| Deploy / create | Create + start gesture | `SettingsGroup` footer or adjacent group + `SettingsInput` / `Select` / primary button |
| Errors / confirms | Safe operator copy | `SettingsNotice` |

## Kit vs panel

| Layer | Owns |
|---|---|
| Accordion / storage kit | Target grammar, cite requirements, safe-field chrome rules |
| SettingsPanel Domains section | Binding to admin domain APIs, expand state, deploy/lifecycle calls |
| `domainSettingsHelpers` | Pure validation, embedding labels, expand toggle, storage label helpers |
| Backend admin DTO | `storageSummary`, domain state, embedding profile id |

## Pseudocode (target — not a dump of live markup)

```tsx
<SettingsGroup title="Knowledge Graphs" description="…">
  {domains.map((domain) => (
    <div key={domain.id}>
      {/* Local Controllers-density row — adapt environment-controls; do not invent Accordion* exports */}
      <div className="/* dense row chrome */">
        <IconButton aria-expanded={…} onClick={…}>{/* chevron */}</IconButton>
        <div>{/* displayName + mono id */}</div>
        <StatusPill>{/* lifecycle */}</StatusPill>
        <ToggleSwitch /* Start XOR Stop */ />
      </div>
      {expanded ? (
        <div role="region">
          <Input readOnly value={`${embeddingLabel} · locked`} />
          {/* Storage: total/limit + one ProgressBar + warning pill (plan 002) */}
          <ProgressBar progress={storageSummary.totalPercent} tone={…} />
          <Button tone="danger">{/* Delete → UiModal confirm */}</Button>
        </div>
      ) : null}
    </div>
  ))}
</SettingsGroup>

<SettingsGroup title="New Knowledge Graph">
  {/* name, id, embedding, Deploy */}
</SettingsGroup>
```

Do **not** treat current hand-rolled `SettingsPanel` JSX as the composition source of truth when it drifts from this map — see [`README.md`](./README.md) drift callouts.
