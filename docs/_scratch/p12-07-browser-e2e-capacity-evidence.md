# P12-07 Browser E2E / Capacity Evidence

Date: 2026-07-29  
Status: **IN_PROGRESS** (not DONE — residuals block AE4/AE5 live / AE9 / AE13 AT / B0)  
Plan: `docs/plans/2026-07-28-015-feat-p12-07-browser-e2e-capacity-plan.md`  
Inventory: `docs/_scratch/p12-07-browser-e2e-capacity-inventory.md`  
Branch tip at evidence write: `feat/p12-07-browser-e2e-capacity` @ `f1ec997` (plus uncommitted U4–U6 harness on working tree — re-pin after commit)

## Prerequisites credited

| Item | Evidence / altitude |
| --- | --- |
| Phase 1 graph contract (U7) | `docs/_scratch/p12-07-phase1-graph-adaptation-inventory.md`; PRD / M-14–M-21 / HTTP+DTO catalogs |
| Extraction binding (U8) | migration `e5b8c1d94f20`; `tests/test_graph_extraction_binding_u8.py` |
| Safe graph API (U9) | `services/graphs.py`; `tests/test_graphs_service_u9.py`, `tests/test_graphs_http_contract.py` |
| Graph workbench (U10) | `src/features/graph/*`; parity `graph-workbench` |
| `scripts/dev.sh` (U11) | `tests/test_dev_sh_u11.py`; runbook note |
| Fixtures (U2) | `npm run fixtures:verify` artifacts; DB `--manifest` world residual |
| P5-04 / P10-05 / P10-06 | cited for live pipeline consume — **not re-proven** in this slice |
| P12-05 TLS live AE | **still IN_PROGRESS** — graph ingress on final topology residual |
| P12-06 SBOM/digests | unit altitude DONE; graph dependency refresh + live Syft residual → P12-08 |

## What landed (this slice)

| Unit | Result |
| --- | --- |
| U1 inventory | Dual-altitude E2E-M/A/C map committed |
| U7–U11 | Contracts → binding → API → workbench → demo entry |
| U2 | Fixture build/verify gate; pump/figure expected artifacts |
| U3 | Playwright `@pr-fast` specs + CI job `verify-playwright-pr-fast` |
| U4 | Gated capacity probe + `@release` specs + checklist; unit L/L+1 graph admission |
| U6 | `@axe-core/playwright` golden routes; visual manifest + fail-closed enforce gate; AT evidence **NO-GO** |
| U5 | This record + tracker honesty (P12-07 not DONE; B0 not complete) |

## Commands (deterministic / local)

```bash
# Graph + capacity unit (no Docker)
cd app
python -m pytest tests/test_graphs_service_u9.py tests/test_graphs_http_contract.py \
  tests/test_graph_extraction_binding_u8.py tests/test_dev_sh_u11.py \
  tests/test_playwright_pr_fast_u3.py tests/test_p12_07_release_capacity_u4.py \
  tests/test_visual_parity_u6.py tests/test_fixtures_u2.py -q

CE_P12_07_RELEASE=1 python scripts/p12_07_release_capacity_probe.py check
CE_P12_07_RELEASE=1 python scripts/p12_07_release_capacity_probe.py unit

python scripts/verify_visual_parity_manifest.py check
# enforce currently fails closed (capture_required) — expected until PNGs approved:
# python scripts/verify_visual_parity_manifest.py enforce --lane pr-fast
```

Observed (2026-07-29, agent workstation): U4 + U6 contract pytest **PASS**; capacity `unit` L+1 → `capacity_unavailable`; visual `enforce --lane pr-fast` → exit 2 `capture_required`.

```bash
# PR-fast Playwright (Compose production Next + BFF + API) — CI job shape
# .github/workflows/verify.yml → verify-playwright-pr-fast
npm --prefix app/client ci
npm --prefix app/client run fixtures:verify
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 npm --prefix app/client run test:e2e:pr-fast
```

Observed: **not re-run end-to-end in this evidence write** (no healthy local Docker matrix at write time). Job wiring + specs are the claimed altitude; green CI digests remain operator residual.

```bash
# @release (opt-in; never default verify.sh)
CE_P12_07_RELEASE=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 \
  npm --prefix app/client run test:e2e:release
# Checklist: docs/_scratch/p12-07-release-evidence-checklist.md
```

## AE matrix (altitude honesty)

| AE | Claim | Altitude |
| --- | --- | --- |
| AE1 inventory complete | YES | doc |
| AE2 fixtures gate | PARTIAL | artifacts verify; DB world residual |
| AE3 PR-fast product paths | PARTIAL | specs + CI job wired; CI green digest residual |
| AE4 visual ≤0.5% | NO | manifest `capture_required`; compare harness ready |
| AE5 capacity L/L+1 | PARTIAL | **unit** graph admission proven; live stream/provider budgets residual |
| AE6 CSRF/BFCache/two-user | PARTIAL | `@pr-fast` specs present; CI digest residual |
| AE7 M-11 open panel | PARTIAL | spec present; CI digest residual |
| AE8 figure answer fixture | PARTIAL | expected fixture + PR path; live prose residual |
| AE9 live Reducto→graph→Evidence→PDF | NO | credential/digest NO-GO unless checklist filled |
| AE10 graph list/URL selection | PARTIAL | `@pr-fast` graph-workbench spec |
| AE11 no browser→LightRAG | PARTIAL | request ban asserts in graph spec |
| AE12 delete/redact graph | residual | @release / service credit |
| AE13 a11y + AT | PARTIAL | axe `@pr-fast` harness; **NVDA/VO NO-GO** |
| AE14 tracker honesty | YES | this file; P12-07 IN_PROGRESS |
| AE15 no Phase 2 observability | YES | scope held |

## DRIFT / B0 disposition

| Row | Browser half | Disposition |
| --- | --- | --- |
| DRIFT-04 | Enabled graph contract + workbench | **Advanced** — U7–U10 landed; deployed E2E digest residual |
| DRIFT-07 | Baseline comparison | **Advanced harness only** — PNG `capture_required`; not closed |
| DRIFT-09 | Named Playwright CI job | **Advanced** — `verify-playwright-pr-fast` exists; green digest + visual approve residual; **B0 not complete** |
| DRIFT-19 | Two-user / logout BFCache | **Advanced** — specs; CI digest residual |
| DRIFT-29 | M-11 open-panel browser | **Advanced** — spec; CI digest residual |
| B0 | Full brownfield gate | **Not complete** — Playwright digest, visual approve, P12-05 TLS live, P12-06 live SBOM, AT pass |

## Graph adaptation (summary)

Closed DTO depth-3 projection; HMAC node refs; admission 429/503; canvas `aria-hidden` with list/detail equivalence; Settings freeze extraction profile at create. See U7 inventory for retain/modify/defer.

## Privacy checklist

- [x] Graph DTO rejects raw `properties` / paths / prompts in unit/HTTP tests  
- [x] `@release` / capacity probe gated out of `scripts/verify.sh`  
- [ ] Failure artifact scan on a green CI Playwright run (residual)  
- [ ] Live provider failure UI request-ID-only proof on `@release` (residual)

## Residuals (owners)

| Residual | Owner |
| --- | --- |
| Approve PNG baselines + `enforce --lane pr-fast` green | P12-07 / FE |
| NVDA+Chrome and VoiceOver+Safari graph task record | P12-07 / a11y operator |
| CI `verify-playwright-pr-fast` green digest on merge revision | P12-07 / CI |
| Live Reducto→extract→graph→chat→Evidence→PDF + capacity AE5 live | P12-07 `@release` + P5-04/P10-05 digests |
| DB fixture `--manifest` world seed | P12-07 U2 residual |
| Graph-aware P12-02/03/04/05/06 revision refresh + SBOM | P12-06/P12-08 |
| P12-05 final TLS topology including graph GETs | P12-05 |
| P12-07 DONE + B0 | blocked on residuals above |

## Explicit non-claims

- P12-07 is **not** DONE.  
- B0 is **not** complete.  
- Visual parity is **not** accepted (`capture_required`).  
- Assistive-technology AE13 is **NO-GO**.  
- Live Reducto/provider prose and full `@release` capacity are **not** claimed from the unit probe.  
- Phase 2 observability / graph mutations / browser→LightRAG are out of scope and not shipped.
