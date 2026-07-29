---
title: "feat: Adopt vehicle-suspension PDF as forward rich corpus fixture"
date: 2026-07-29
status: active
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
execution: code
---

# Adopt vehicle-suspension PDF as forward rich corpus fixture

## Goal Capsule

- **Objective:** Lock `doc_vehicle_suspension` (`app/tests/fixtures/documents/Vehicle_Suspension_System_Technology_And_Design_TEST.pdf`) as the forward standard corpus for live upload → parse → index → retrieval → Evidence (text/table/figure) → grounded synthesis proofs, and point open Phase 12 / parser plans at that fixture.
- **Authority:** `docs/quality/seeded-demo-and-test-data.md` (Documents and canonical anchors — rich live corpus); root `AGENTS.md` privacy/fixture rules; P12-07 `@release` pipeline; P4-05 region provenance live residual.
- **Execution profile:** Docs + fixture placement first; consumers (preflight, `@release` demos, live parser/Evidence tests) adopt the path/hash in follow-on slices without inventing a second ad-hoc PDF.
- **Stop conditions:** Do not replace deterministic PR-fast fixtures (`doc_pump_manual`, `doc_safety_bulletin`, exact Mina answer strings). Do not claim exact provider prose. Do not put the PDF outside `tests/fixtures/documents/`. Do not seed this corpus in production.

## Product / engineering contract

**F1 — Single rich corpus.** All new live/operator tests for multi-modal Evidence and synthesis use `doc_vehicle_suspension` unless a case explicitly needs a smaller or adversarial fixture.

**F2 — Dual altitude preserved.** PR-fast continues to use synthetic seed PDFs and deterministic adapters. `@release` / Compose live may use `doc_vehicle_suspension` with real parsers and providers.

**F3 — Hash-gated identity.** Consumers pin SHA-256 `8fbda29d44b910e997f8235ab6bb5d5b61419a5b80ef965793738656920688b8` (1680934 bytes). Changing bytes requires a reviewed manifest/expected/plan update.

## Requirements

- R1. Fixture bytes live at `app/tests/fixtures/documents/Vehicle_Suspension_System_Technology_And_Design_TEST.pdf` with fixture key `doc_vehicle_suspension`.
- R2. `docs/quality/seeded-demo-and-test-data.md` records path, hash, size, and intended coverage.
- R3. P12-07 `@release` admin→upload→parse→graph/index→chat→Evidence→PDF demo cites this corpus for the rich-PDF path (pump/safety fixtures remain PR-fast authority).
- R4. P4-05 live/region/Evidence follow-ups that need a real multi-block PDF cite this corpus.
- R5. Operator helpers (e.g. stack live preflight) prefer this fixture when exercising parser/index/Evidence lanes.
- R6. Future expected Evidence anchors for text/table/figure from this PDF are added under `tests/fixtures/expected/` in the owning implementation slice — not invented in this planning-only close unless measured.

## Acceptance examples

- AE1. Fixture path exists; SHA-256 matches the seeded-demo table.
- AE2. P12-07 / P4-05 plans (and this plan) name `doc_vehicle_suspension` for rich live Evidence coverage.
- AE3. No plan or helper treats a repo-root ad-hoc `Vehicle_Suspension_*.pdf` as authority.

## Implementation Units

### U1. Place and authority-document the fixture

**Goal:** Commit the PDF under fixtures and freeze identity in seeded-demo.

**Files:**
- Create: `app/tests/fixtures/documents/Vehicle_Suspension_System_Technology_And_Design_TEST.pdf`
- Modify: `docs/quality/seeded-demo-and-test-data.md`

**Verification:** Hash/size match AE1; PR-fast synthetic table unchanged.

### U2. Retarget open plans and helpers

**Goal:** Point consumers at the fixture key/path.

**Files:**
- Modify: `docs/plans/2026-07-28-015-feat-p12-07-browser-e2e-capacity-plan.md`
- Modify: `docs/plans/2026-07-28-008-feat-p4-05-region-provenance-plan.md`
- Modify: `app/scripts/_p12_05_live_domain_preflight.py` (prefer rich fixture when present)
- Modify: `docs/operations/compose-stack-runbook.md` (one-line corpus pointer under live/TLS preflight if needed)

**Verification:** Plans and helper cite `doc_vehicle_suspension`; no authority claim for repo-root copies.

### U3. (Follow-on) Freeze measured Evidence expectations

**Goal:** After a measured live prepare/index pass, record stable expected Evidence kinds/anchors for text/table/figure under `tests/fixtures/expected/` and wire `@release` assertions.

**Dependencies:** U1–U2; live parser availability

**Execution note:** Characterization-first — capture real mapped Evidence projections before locking expected JSON. Out of scope for the docs-only landing of U1–U2 if measurement is not run in the same slice.

## Definition of Done (this slice)

- Fixture committed under `tests/fixtures/documents/` with seeded-demo identity table.
- P12-07 and P4-05 cite the corpus for rich live Evidence/synthesis work.
- Operator preflight prefers the fixture when present.
- Residuals named: measured expected anchors (U3), page-count/manifest entry when `fixtures:build` lands under P12-07 U2.

## Sources

- Operator designation 2026-07-29: use `Vehicle_Suspension_System_Technology_And_Design_TEST.pdf` going forward for upload/parsing/retrieval/Evidence/synthesis tests.
- `docs/quality/seeded-demo-and-test-data.md`
- `docs/plans/2026-07-28-015-feat-p12-07-browser-e2e-capacity-plan.md`
- `docs/plans/2026-07-28-008-feat-p4-05-region-provenance-plan.md`
