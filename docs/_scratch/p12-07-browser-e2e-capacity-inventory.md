# P12-07 Browser E2E / Capacity Inventory

Date: 2026-07-28

Owner: P12-07 U1

Status: IN_PROGRESS — U1–U11 + U5 evidence recorded; P12-07 not DONE — PNG `capture_required`, AT NO-GO, CI/live `@release` digests residual; B0 not complete

Plan: `docs/plans/2026-07-28-015-feat-p12-07-browser-e2e-capacity-plan.md`

Authority: `docs/frontend/browser-e2e-scenarios.md`; `docs/interaction-behavior-prd.md` M-14–M-21;
`docs/quality/seeded-demo-and-test-data.md`; DRIFT-04/07/09/19/29.

## Disposition legend

| Disposition | Meaning |
| --- | --- |
| PR-fast | Playwright on every PR: deterministic adapters + real Next/BFF/API/worker/PG/object store |
| @release | Gated live Reducto/provider/LightRAG + capacity + full visual; out of default `verify.sh` |
| credit | Existing real-boundary proof cited; browser residual not required for this invariant |
| residual | Named owner / later unit; not claimed DONE by this row |

## Altitude rules

| Lane | Stack | Providers |
| --- | --- | --- |
| PR-fast | Production Next + BFF + API + worker + PG16 + governed object store | Deterministic parser/embedding/extraction adapters + private fixture runtime |
| @release | Same + `compose.stack.live.yml` (+ MinIO/preview/provider gates) | Live Reducto, supported embedding/extraction, private LightRAG |

Harness: separate `BrowserContext` per actor; sync on responses/SSE/op/DB hooks; never fixed sleeps.
Public origin must be `127.0.0.1`. Fault plane requires `CE_ENVIRONMENT=test` + `CE_ALLOW_TEST_FAULTS=true` and is absent from production images.

---

## Member E2E matrix

| E2E ID | Case | Altitude | Fixture keys | Credit / residual | DRIFT |
| --- | --- | --- | --- | --- | --- |
| E2E-M01 | M-01 | PR-fast | Ava/Mina login actors | CSRF product path proof (not API-only) | 19 |
| E2E-M02 | M-02 | PR-fast | `domain_manuals`, draft chat | — | — |
| E2E-M03 | M-03 | PR-fast | `turn_mina_*`, SSE fixtures | Producer/reducer credited P7/P9-02 | — |
| E2E-M04 | M-04 | PR-fast | `ev_mina_figure_valve`, page 18 | — | — |
| E2E-M05 | M-05 | PR-fast | `ev_mina_text_lockout`, table, page-only | — | — |
| E2E-M06 | M-06 | PR-fast | delayed T1 fault barrier | — | — |
| E2E-M07 | M-07 | PR-fast | direct + domain_required drafts | — | — |
| E2E-M08 | M-08 | PR-fast | Mina/Noah conversations | Vitest workflows P9-07 | — |
| E2E-M09 | M-09 | PR-fast | source/template tokens | Evidence attach DEFERRED P11-04 | — |
| E2E-M10 | M-10 | PR-fast | dual-tab same fingerprint | PG races credited P7 | — |
| E2E-M11 | M-11 | PR-fast | open PDF + Ava delete | API redaction credited P12-03; **browser open-panel required** | 29 |
| E2E-M14 | M-14 | PR-fast | graph snapshot fixtures | U7–U10 product path | 04 |
| E2E-M15 | M-15 | PR-fast | relief-valve node | U10 list/canvas/URL | 04 |
| E2E-M16 | M-16 | PR-fast | Noah cross-domain | Service 404 credited; browser shape required | 04 |
| E2E-M17 | M-17 | PR-fast | stopped/unready domains | — | 04 |
| E2E-M18 | M-18 | PR-fast (+ @release delete path) | delete reconcile barrier | — | 04/29 |
| E2E-M19 | M-19 | @release (admission) | graph permit budgets | Unit admission may credit U9 | — |
| E2E-M20 | M-20 | PR-fast | truncated snapshot fixture | — | 04 |
| E2E-M21 | M-21 | PR-fast | graph list/detail | A11y U6 | 04/07 |

M-12/M-13 remain tombstoned — not reused.

---

## Administrator E2E matrix

| E2E ID | Case | Altitude | Disposition |
| --- | --- | --- | --- |
| E2E-A01 | A-01 | PR-fast | Settings credential presence-only + ETag conflict |
| E2E-A02 | A-02 | PR-fast | Immutable embedding + extraction reject mutate |
| E2E-A03 | A-03 | PR-fast | Create/start reconcile incl. extraction binding |
| E2E-A04 | A-04 | PR-fast / credit | Stop-during-query terminal policy; service credit OK if UI observes fence |
| E2E-A05 | A-05 | credit (+ UI if observable) | PG generation races credited; browser only if dual-admin UI shown |
| E2E-A06 | A-06 | credit | Upload dedupe — service/PG |
| E2E-A07 | A-07 | credit | Prep retry races — service/PG |
| E2E-A08 | A-08 | PR-fast smoke | Index readiness eligibility before query/graph |
| E2E-A09 | A-09 | PR-fast | Source delete UX + cleanup-visible; ties M-11/M-18 |
| E2E-A10 | A-10 | PR-fast | Domain delete selection clear + recoverable failure |
| E2E-A11 | A-11 | credit | Frozen defaults — service credit; browser optional |

P9-04 Settings domains F3 (production-boundary) is **PR-fast** and distinct from Key Flow F3.

---

## Concurrent E2E matrix

| E2E ID | Case | Altitude | Notes |
| --- | --- | --- | --- |
| E2E-C01 | C-01 | @release | N≥2 members; transcript/evidence/graph/request-ID isolation; L/L+1 shed |
| E2E-C02 | C-02 | PR-fast | Stale list → safe unavailable |
| E2E-C03 | C-03 | PR-fast | Dual-anchor document viewers independent |
| E2E-C04 | C-04 | PR-fast | Cross-owner nondisclosure incl. graph |
| E2E-C05 | C-05 | PR-fast | Role revoke via test hook |

---

## CSRF / cache / Settings / visual / a11y

| Surface | Altitude | Notes | DRIFT |
| --- | --- | --- | --- |
| CSRF product path (login rotation, unsafe POST via BFF) | PR-fast | Proof-first; client already attaches token | — |
| Two-user cache / BFCache / logout Back | PR-fast | Separate jars; `private, no-store` | 19 |
| Settings `/settings?section=domains` F3 | PR-fast | Server DTOs; embedding+extraction selectors | — |
| Visual laptop+mobile dark/light baselines | PR-fast | ≤0.5%; catalog `targetId` linkage | 07 |
| Visual full matrix + zoom | @release | tablet/desktop/wide/320/200%/400% | 07 |
| Axe + keyboard critical paths | PR-fast | Incl. graph list/detail (M-21) | — |
| Named Playwright CI job | PR-fast | Advances DRIFT-09 E2E half / B0 | 09 |

---

## Pipeline / capacity / preview (@release)

| Surface | Altitude | Consumes | Notes |
| --- | --- | --- | --- |
| Reducto→blocks→extract/index→graph→chat→Evidence→PDF | @release | P5-04, P10-05, P10-06 | AE8/AE9/AE10; no triad product |
| Governed non-PDF preview nav/failure | PR-fast smoke + @release failure | P10-06 | R9 |
| Runtime/provider/parser/extraction failure UI | @release | — | request ID; no private URLs |
| Capacity L/L+1 stream+graph admission | @release | U9 admission, P8-03 codes | AE5; freeze budgets in evidence |
| `scripts/dev.sh` lean demo | operator | U11 | AE15 |

---

## Credits from prior slices

| Prior | Credit | Does **not** close |
| --- | --- | --- |
| P9-07 | Vitest rename/refs/provider/history | Production Playwright |
| P9-05 | BFF `private, no-store` | Two-user BFCache browser |
| P12-03 | API M-11 redaction/adversarial | Open-panel/cache browser |
| P5-04 | Two-domain LightRAG isolation | Browser/capacity consume |
| P10-05/P10-06 | Packaging + preview generation | Browser navigation/failure |
| P12-02 | `verify.sh` + PG CI | Playwright job / B0 |
| U7 | Authority graph contract | Runtime/API/UI/E2E |
| U8 | Extraction binding + private graph ops | Public HTTP / workbench |

---

## CSRF residual classification

| Hypothesis | Disposition |
| --- | --- |
| Client attach already correct; residual is E2E proof + origin (`127.0.0.1`) | **Default** — prove before inventing fixes |
| Bootstrap/login CSRF rotation edge | Fix only if product path fails live |
| Cookie SameSite/path misconfig in Compose | Ops/wiring if proven |

---

## Worklist by unit

| Unit | Inventory obligation |
| --- | --- |
| U2 | Materialize seeded-demo + graph fixture keys |
| U3 | PR-fast Playwright rows above + CSRF/Settings/M-11/graph |
| U4 | @release pipeline/capacity/failure |
| U6 | A11y `@pr-fast` + visual manifest/gate landed; PNG `capture_required`; AT NO-GO |
| U5 | Evidence; close DRIFT halves only where proven |
| U10–U11 | Enabled workbench + `dev.sh` before full U3 graph acceptance |

## Explicit non-claims

- Phase 2 observability / RAG-triad metric product
- Graph mutation APIs
- Browser→LightRAG or direct `/graphs`
- B0 complete solely from this inventory
- P12-05 TLS digests / P12-06 live Syft as owned by this inventory
