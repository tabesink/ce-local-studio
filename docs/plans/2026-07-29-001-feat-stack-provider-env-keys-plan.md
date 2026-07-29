---
title: Stack Provider Env Keys for Host Testing - Plan
type: feat
date: 2026-07-29
topic: stack-provider-env-keys
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
phase_compatibility: phase-1-active
---

# Stack Provider Env Keys for Host Testing - Plan

## Goal Capsule

- **Objective:** Make OpenAI and Reducto API keys available to existing host testing gates from the canonical gitignored stack env file, with unprefixed names documented in the stack example and aligned operator docs.
- **Product authority:** Root `AGENTS.md` (credentials never committed; privacy by construction); `docs/operations/compose-stack-runbook.md`; `docs/operations/provider-deployment-profiles.md`; existing host gates in provider staging smoke and TLS/SSE proof scripts.
- **Execution profile:** Docs + small host-script ergonomics; smoke-first / contract-test verification. Do not touch product Settings seal paths or Compose service env.
- **Readiness checkpoint:** Implementation-ready after planning chose optional `--env-file` on staging smoke (parity with SSE proof).
- **Open blockers:** None.
- **Stop conditions:** Stop if work would inject provider keys into Compose api/worker, auto-seal env keys into DB credentials, or invent new host gates beyond staging smoke and TLS/SSE proof.

---

## Product Contract

### Summary

Fold OpenAI and Reducto test API keys into `.env.stack.local` as the sole supported local file. Document unprefixed `OPENAI_API_KEY` and `REDUCTO_API_KEY` in the stack example, align host-gate runbooks, and migrate operators off `app/.env` via documentation only. Product provider use still requires sealed Settings credentials; Compose services do not receive these keys.

**Product Contract preservation:** Product Contract unchanged (R/A/F/AE IDs preserved). Planning resolved the deferred staging-smoke load path as optional `--env-file` (KTD1); F1 steps remain compatible.

### Problem Frame

Operators already need live OpenAI and Reducto credentials for credential-gated host tests, but the stack example and runbooks do not present a single first-class place for those names. A separate `app/.env` appeared as a workaround, splitting secrets across files and making it unclear what host scripts actually load. Meanwhile, product chat/parse still depends on admin-sealed credentials — so env consolidation must not be mistaken for auto-wiring providers into the running product.

### Key Decisions

- **Env consolidation only.** Keys enable host testing access; they do not auto-seal into encrypted product credentials on start.
- **Canonical file: `.env.stack.local` only.** `app/.env` is unsupported going forward; migration guidance is docs-only (no runtime warning).
- **Host scripts only.** Existing provider staging smoke and TLS/SSE proof paths; no Compose api/worker injection of provider keys.
- **Documented names are unprefixed.** `OPENAI_API_KEY` and `REDUCTO_API_KEY` are the stack-local standard; `CE_*` aliases may remain accepted by scripts but are not the preferred documented names.
- **Approach B.** Example placeholders plus alignment of the compose/provider docs that already describe those host gates.

### Actors

| ID | Actor | Role |
| --- | --- | --- |
| A1 | Local operator / developer | Copies example to `.env.stack.local`, sets keys, runs host gates |
| A2 | Coding agent / maintainer | Updates example + runbook surfaces; never commits key values |

### Key Flows

- F1. Fresh local setup for live host gates
  - **Trigger:** Operator wants to run an existing credential-gated host test.
  - **Actors:** A1
  - **Steps:** Recreate or update `.env.stack.local` from `.env.stack.example`; set `OPENAI_API_KEY` and/or `REDUCTO_API_KEY` as needed; run the existing host gate with `--env-file` pointing at that file (SSE proof already; staging smoke gains the same flag); gate authenticates when the required key is present.
  - **Outcome:** Live host gate proceeds past the credential presence check without needing `app/.env`.
  - **Covered by:** R1, R2, R3, R5

- F2. Stack boot without provider keys
  - **Trigger:** Operator starts the Compose/dev stack without OpenAI/Reducto keys set.
  - **Actors:** A1
  - **Steps:** Stack boots using non-provider stack secrets as today.
  - **Outcome:** Missing provider keys do not block ordinary stack start; only live host gates that require them refuse.
  - **Covered by:** R4

### Requirements

**Canonical env surface**

- R1. `.env.stack.example` documents optional `OPENAI_API_KEY` and `REDUCTO_API_KEY` placeholders for host testing, with guidance never to commit working values.
- R2. `.env.stack.local` is the only supported local file for those keys; operator docs state that `app/.env` is unsupported and keys should be moved into `.env.stack.local`.

**Host testing consumers**

- R3. Existing host gates continue to credential-gate on the unprefixed names (and any aliases they already accept): TLS/SSE proof for OpenAI; provider staging smoke for OpenAI and Reducto. Operators place keys in `.env.stack.local`; both gates accept `--env-file` for that file so process env is populated before the credential check — do not invent new gates.
- R4. Ordinary stack start does not require provider keys; absence only fails the live host gates that already refuse without credentials.
- R5. Docs for those host gates name unprefixed `OPENAI_API_KEY` / `REDUCTO_API_KEY` and `.env.stack.local`, and restate that host env keys are necessary for gated live tests but not sufficient for sealed product provider use (Settings / admin credential path remains separate).

**Safety and non-goals as requirements**

- R6. Provider key values never appear in committed examples, logs, proof output, or evidence artifacts — names and presence only.
- R7. Compose api/worker (and other stack services) are not given these provider keys as part of this work.

### Acceptance Examples

- AE1. Optional keys present
  - **Covers:** R1, R3, R5
  - **Given:** `.env.stack.local` contains a non-empty `OPENAI_API_KEY` (and `REDUCTO_API_KEY` when the Reducto staging profile is used), and the operator runs the gate with `--env-file` for that file.
  - **When:** Operator runs an existing OpenAI- or Reducto-gated host script for that profile.
  - **Then:** The script’s credential presence check passes; no key material is printed.

- AE2. Keys absent
  - **Covers:** R4
  - **Given:** Provider keys are unset in `.env.stack.local` and process env.
  - **When:** Operator starts the stack, then attempts a live host gate that requires OpenAI or Reducto.
  - **Then:** Stack start still succeeds; the host gate refuses before network use as it does today.

- AE3. Unsupported `app/.env`
  - **Covers:** R2
  - **Given:** Operator docs after this change.
  - **When:** A reader looks for where to put OpenAI/Reducto test keys.
  - **Then:** Docs point only at `.env.stack.local` / the stack example and say `app/.env` is unsupported (no requirement that tools auto-detect or warn).

- AE4. Product credentials unchanged
  - **Covers:** R5, R7
  - **Given:** Keys exist only in `.env.stack.local` and are not sealed via Settings.
  - **When:** Operator uses product chat/parse paths that require sealed provider credentials.
  - **Then:** Behavior remains governed by sealed Settings credentials; this work does not claim those paths become ready from env alone.

### Scope Boundaries

**In scope**

- Stack example placeholders for unprefixed OpenAI/Reducto keys
- Docs-only migration off `app/.env`
- Alignment of compose/provider host-gate documentation for existing gates
- Optional `--env-file` on provider staging smoke (parity with SSE proof)

**Out of scope**

- Auto-sealing env keys into encrypted DB provider credentials on bootstrap/start
- Injecting OpenAI/Reducto keys into Compose api/worker (or other services)
- Runtime warning when leftover `app/.env` exists
- New testing surfaces beyond existing host gates
- Changing product Settings / credential-rotate contracts
- Preferring or documenting `CE_*` names as the stack-local standard
- Approach C (rewriting all missing-key messages to unprefixed-only) — deferred follow-up

### Dependencies / Assumptions

- Existing host scripts already accept unprefixed and/or `CE_*` OpenAI/Reducto env names for credential gates.
- Product provider calls continue to use sealed admin credentials; runbooks already distinguish host env presence from sealed synthesis readiness.
- `.env.stack.local` remains gitignored; examples never carry real key values.
- SSE proof already merges `--env-file` before its OpenAI credential gate; staging smoke does not yet.

---

## Planning Contract

### Key Technical Decisions

- KTD1. **Staging smoke gains optional `--env-file`.** Default Path is script-relative (`Path(__file__).resolve().parents[1] / ".env.stack.local"`, same as SSE proof) — not a cwd-dependent `app/` string. Parse/merge before live credential checks using the SSE-proof helpers (`_load_env_file` + merge-if-unset for secret keys). **Divergence from SSE:** if the env file is missing, soft-skip (do not fail); only refuse live mode when credentials are still absent after merge. Include OpenAI and Reducto unprefixed and `CE_*` names in the secret allowlist so Reducto keys from the file actually land in process env. Do not extract a shared library in this slice unless duplication becomes painful — copy the small helpers.
- KTD2. **Document unprefixed names; keep script alias acceptance.** Example and runbooks lead with `OPENAI_API_KEY` / `REDUCTO_API_KEY`. Scripts continue to accept `CE_*` fallbacks where they already do. Provider-deployment-profiles live examples switch headline env to unprefixed (or show stack-file + `--env-file`) rather than leading with `CE_*`.
- KTD3. **Example presentation: commented optional block.** Add a short “Host live-test credentials (optional)” comment block with `OPENAI_API_KEY=` / `REDUCTO_API_KEY=` placeholder lines (empty or `<set locally>` — never real values), noting host gates only, never commit, not sealed Settings, and that Compose services do not consume these keys.
- KTD4. **Contract tests, not live network.** Assert example documents the two assignment lines and host-gate wording; extend staging-smoke tests to prove `--env-file` supplies credentials for the refuse/pass gate without printing values. No root-verify live provider calls.

### Assumptions

- Operators will recreate or edit `.env.stack.local` from the updated example; this plan does not migrate their existing `app/.env` automatically.
- Dual-name acceptance in scripts is enough for back-compat; documenting only unprefixed names will not break operators who still export `CE_*`.

### Alternative Approaches Considered

| Approach | Why not chosen |
| --- | --- |
| Docs-only `set -a` / export for staging smoke | Weaker ergonomics; easy to miss; user selected `--env-file` parity |
| Shared `context_engine` env-file helper module | Extra surface for a two-script copy; defer until a third consumer needs it |
| Auto-seal env keys at bootstrap | Explicitly out of product scope for this brainstorm |

### Risks and Dependencies

| Risk | Mitigation |
| --- | --- |
| Operators think keys in stack env make chat/parse work | R5 / AE4 restated in example + runbooks |
| Secret leakage in test/stdout | Never assert key values; keep refuse messages name-only; strip parent env in subprocess tests |
| Example test brittle on comment wording | Assert stable substrings (`OPENAI_API_KEY=`, `REDUCTO_API_KEY=`, host-test / never-commit cues) |

---

## Implementation Units

### U1. Stack example placeholders + contract assert

- **Goal:** `.env.stack.example` documents optional unprefixed OpenAI/Reducto keys for host testing; compose-config tests lock the documentation.
- **Requirements:** R1, R6, R7
- **Dependencies:** None
- **Files:**
  - Modify: `app/.env.stack.example`
  - Modify: `app/tests/test_compose_stack_config.py`
- **Approach:** Add KTD3 comment block with empty/`<set locally>` assignment lines for `OPENAI_API_KEY` and `REDUCTO_API_KEY`. Align nearby SSE proof comment to prefer unprefixed names (aliases may still be noted as accepted by scripts). Add a focused test that the example contains those assignment lines and states they are optional host-test credentials not for Compose services / not sealed Settings.
- **Execution note:** Prefer contract substring asserts over live stack boots.
- **Patterns to follow:** Existing `test_env_example_*` tests in `app/tests/test_compose_stack_config.py`.
- **Test scenarios:**
  - Happy path: example text includes `OPENAI_API_KEY=` and `REDUCTO_API_KEY=` lines and a host-test / never-commit cue.
  - Edge: example does not contain a realistic-looking committed secret value for those keys (placeholders only).
- **Verification:** New/updated compose-stack config tests pass; example remains free of real key material.

### U2. Staging smoke `--env-file` merge before credential gate

- **Goal:** `provider_staging_smoke.py` can load `.env.stack.local` the same way SSE proof does, so OpenAI/Reducto keys in that file satisfy live gates.
- **Requirements:** R3, R6; AE1
- **Dependencies:** None (can parallel U1; docs in U3 may reference the flag)
- **Files:**
  - Modify: `app/scripts/provider_staging_smoke.py`
  - Modify: `app/tests/test_provider_staging_smoke.py`
- **Approach:** Per KTD1, add `--env-file` with script-relative default (`Path(__file__).resolve().parents[1] / ".env.stack.local"`). Load/merge before `require_live_credentials` / live mode credential resolution. Missing file: soft-skip (unlike SSE hard-fail); refuse live mode only when credentials are still missing after merge. Never print key values. Keep existing `CE_*` then unprefixed lookup order in `_credential_for_profile`.
- **Execution note:** Extend subprocess tests with a temp env file; strip parent credential env as today.
- **Patterns to follow:** `app/scripts/stack_ingress_sse_proof.py` `_load_env_file` / `_merge_env_file` / pre-gate merge; existing `_run` helper in `test_provider_staging_smoke.py`.
- **Test scenarios:**
  - Covers AE1: live mode with gate set, credentials only in `--env-file` as `OPENAI_API_KEY`, passes credential presence (or reaches the next non-credential refuse) without printing the key.
  - Covers AE1 (Reducto): same for reducto profile with `REDUCTO_API_KEY` only in the env file.
  - Error path: live mode, empty/missing keys in file and process env → existing credential refuse, message names env vars not values.
  - Edge: process env already has key; env-file also has different value → merge-if-unset preserves process env (SSE pattern).
  - Happy path regression: existing gate_refused / check mode tests still pass without requiring `--env-file`.
- **Verification:** `test_provider_staging_smoke.py` green; manual dry-run of refuse path shows no secret material.

### U3. Operator doc alignment (Approach B)

- **Goal:** Compose runbook and provider deployment profiles tell one story: unprefixed keys in `.env.stack.local`, `app/.env` unsupported, host gates via `--env-file`, Settings seal still required for product providers.
- **Requirements:** R2, R5; AE3, AE4
- **Dependencies:** U2 (so docs can name smoke `--env-file` accurately); U1 for example wording consistency
- **Files:**
  - Modify: `docs/operations/compose-stack-runbook.md`
  - Modify: `docs/operations/provider-deployment-profiles.md`
  - Optionally touch: `app/client/tests/e2e/README.md` only if it currently implies a different provider-key file (keep minimal)
- **Approach:** Update TLS/SSE and staging-smoke sections to prefer `OPENAI_API_KEY` / `REDUCTO_API_KEY` in `.env.stack.local`, show `--env-file .env.stack.local` for both gates, state `app/.env` is unsupported for Context Engine stack operator credentials, and keep the “host key ≠ sealed synthesis” warning. Replace headline `CE_*` examples in provider-deployment-profiles with unprefixed + stack-file guidance; note `CE_*` still accepted if already set.
- **Execution note:** Documentation/smoke verification — no new network tests.
- **Patterns to follow:** Existing TLS boot comment block in compose-stack-runbook; credential-gated wording in P12-05 evidence notes (names only).
- **Test scenarios:**
  - Test expectation: none — documentation unit; completeness checked by review against R2/R5/AE3/AE4.
- **Verification:** Grep/read shows no remaining operator instruction that `app/.env` is the stack provider-key path; live smoke examples mention `.env.stack.local` and unprefixed names.

---

## Verification Contract

- **Unit / contract:** `app/tests/test_compose_stack_config.py` (U1); `app/tests/test_provider_staging_smoke.py` (U2).
- **Docs:** Manual read of compose-stack-runbook + provider-deployment-profiles against R2/R5/AE3/AE4 (U3).
- **Privacy:** No test, log, or evidence artifact contains real provider key values; fail messages remain name/presence only.
- **Non-claims:** Do not claim product chat/parse works from env alone; do not claim Compose injects these keys; do not require live OpenAI/Reducto in root `verify.sh`.

---

## Definition of Done

- R1–R7 satisfied; AE1–AE4 outcomes reachable from docs + host scripts.
- U1–U3 complete with listed verification.
- Product Contract IDs preserved; no Compose provider-key injection; no auto-seal.
- Operator can place keys only in `.env.stack.local` and run staging smoke / SSE proof with `--env-file` without using `app/.env`.

---

## Appendix

### Sources & Research

- Repo research: SSE proof `_load_env_file` / `_merge_env_file` at `app/scripts/stack_ingress_sse_proof.py`; staging smoke credential lookup at `app/scripts/provider_staging_smoke.py` (no `--env-file` today); example tests in `app/tests/test_compose_stack_config.py`; provider profiles doc leads with `CE_*`.
- Claim check (brainstorm): staging smoke process-env only; SSE OpenAI via `--env-file`; no Compose injection; no bootstrap seal.
- Institutional `docs/solutions/`: absent.
- Grounding dossier (brainstorm): `/tmp/compound-engineering/ce-brainstorm/provider-env-1785327144/grounding.md` (ephemeral).
