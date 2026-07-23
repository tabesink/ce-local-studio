# Frontend UIUX Component Factory

Agent- and junior-facing catalog for **Context Engine** UI.
Use this folder **with** root [`DESIGN.md`](../../DESIGN.md) — never instead of it.
Visual authority is Local Studio parity (`--ui-*`, Geist, dense workstation), not a generic shadcn/zinc dashboard.

## Read order (agents)

1. [`AGENTS.md`](./AGENTS.md) — operating rules
2. [`theme.md`](./theme.md) — terse theme / atmosphere pointer
3. Matching feature folder under this tree
4. [`shared/`](./shared/) when the work touches reusable kits (accordion/storage, …)
5. [`DESIGN.md`](../../DESIGN.md) for tokens, live kit inventory, and not-in-kit gaps

## Catalog

| Folder | Status | What it covers |
|---|---|---|
| [`shared/`](./shared/) | **Active** (kit docs; Controllers accordion/storage **not exported yet**) | Cross-feature UI kits |
| [`settings/knowledge-graphs/`](./settings/knowledge-graphs/) | **Complete (v1)** | Settings → Knowledge Graphs worked example |
| [`app-shell/`](./app-shell/) | Stub | Sidebar, shell, nav chrome |
| [`chat/`](./chat/) | Stub | Chat shell + evidence |
| [`documents/`](./documents/) | Stub | Document library |
| [`graph/`](./graph/) | Stub | Graph workspace |
| [`settings/`](./settings/) | Stub | Settings panel shell |
| [`user-preferences/`](./user-preferences/) | Stub | Appearance / theme runtime |
| [`_templates/`](./_templates/) | Template | Copy for new feature packs |

## Related plans

- Factory requirements + execution: [`docs/plans/2026-07-13-001-feat-frontend-uiux-component-factory-plan.md`](../plans/2026-07-13-001-feat-frontend-uiux-component-factory-plan.md)
- KG structure / safe fields: [`docs/plans/2026-07-10-006-feature-domain-deploy-settings-ui-plan.md`](../plans/2026-07-10-006-feature-domain-deploy-settings-ui-plan.md)
- KG Controllers density polish (live remediation — out of factory scope): [`docs/plans/2026-07-11-002-feature-knowledge-graphs-settings-parity-polish-plan.md`](../plans/2026-07-11-002-feature-knowledge-graphs-settings-parity-polish-plan.md)
- Design kit inventory / Controllers gap: [`docs/plans/2026-07-11-003-feature-design-kit-contract-inventory-plan.md`](../plans/2026-07-11-003-feature-design-kit-contract-inventory-plan.md)

## Status legend

- **Stub** — folder + short README only; invent nothing beyond `DESIGN.md` + existing CE code
- **Active** — reusable kit documented; implement against it (may still be **not exported yet**)
- **Complete (v1)** — enough to implement the surface without inventing layout grammar
