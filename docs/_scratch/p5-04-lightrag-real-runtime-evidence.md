# P5-04 Real Per-Domain LightRAG Runtime Evidence

Date: 2026-07-28

Owner: P5-04

Status: DONE — dual-lane proofs recorded

Plan: `docs/plans/2026-07-28-006-feat-p5-04-real-lightrag-runtime-plan.md`

Inventory: `docs/_scratch/p5-04-lightrag-real-runtime-inventory.md`

## Artifact revision

Branch: `feat/p5-04-real-lightrag-runtime`

Live image tag used for proofs: `context-engine-live:local` (Dockerfile `CE_STACK_LIVE_IMAGE=1`)

## Dual-lane matrix

| Lane | Controller | Client | Gate |
| --- | --- | --- | --- |
| Default CI / `compose.stack.yml` | `local` | `local` | Root `scripts/verify.sh` (no live Docker required) |
| Live overlay `compose.stack.live.yml` | `docker` | `native` | Opt-in `CE_P5_04_LIVE=1` + live image |

## Commands run

### Always-on / CI-safe

```bash
cd app
.venv/bin/python -m pytest tests/test_compose_stack_config.py tests/test_lightrag_http_client.py tests/test_source_index_eligibility.py tests/test_domain_runtime_controller_tool.py -q
.venv/bin/python -m pytest tests/test_lightrag_real_runtime_integration.py -q   # skips live case without CE_P5_04_LIVE
```

Compose config (default stays local/local; overlay pins docker/native):

```bash
cd app
docker compose -f compose.stack.yml config >/dev/null
CE_STACK_LIVE_RUNTIME_ROOT=/tmp/ce-p5-04-live-runtime-config \
  CE_DOMAIN_CONTROLLER_IMAGE=context-engine-live:local \
  docker compose -f compose.stack.yml -f compose.stack.live.yml config >/dev/null
```

### Live lane (opt-in)

```bash
cd app
docker build --build-arg CE_STACK_LIVE_IMAGE=1 -t context-engine-live:local .
CE_P5_04_LIVE=1 CE_DOMAIN_CONTROLLER_IMAGE=context-engine-live:local \
  .venv/bin/python -m pytest tests/test_lightrag_real_runtime_integration.py -q
```

Result (2026-07-28): `2 passed` — always-on dual-lane skip guard + live submit→ready→retrieve→delete/absence, parallel two-domain isolation, warm restart, zero host-published bindings, schema-v2 markers retained through retrieve.

## Acceptance mapping

| AE | Result |
| --- | --- |
| AE1 Inventory | Credit/replace frozen in inventory scratch |
| AE2 Two private healthy runtimes, no host ports | Live test asserts health + empty host port bindings; peer reachability on `ce-domain-runtimes` |
| AE3 Submit→ready→mapped chunks with schema-v2 | Live test |
| AE4 Uncertain recovery | Credited to P5-03 worker path; U4 gate preserves readiness-probe before re-submit; transport timeout unit coverage retained |
| AE5 Delete/absence | Live test |
| AE6 Two-domain isolation | Live concurrent index/retrieve; cross-marker absence |
| AE7 Default verify without live Docker | `CE_P5_04_LIVE` absent from `scripts/verify.sh`; default Compose remains `local`/`local` |
| AE8 Tracker / DRIFT-27 | Closed for production path via per-container isolation; in-process synthetic residual documented |

## Privacy notes

- Live proofs use `docker exec` loopback transport from the host test process; production API/worker reach runtimes on the private Docker network only.
- No runtime URLs, sealed provider credentials, or handoff dumps appear in public DTOs/SSE (unchanged contract).
- Sealed provider env remains mode-`600` under the domain bind mount (U2/U3).

## Residuals (named owners)

| Residual | Owner |
| --- | --- |
| Empty-volume rebuild / backup-restore drills | Cite-closed under P12-04 (`docs/_scratch/p12-04-backup-restore-evidence.md`); Compose live rebuild digests residual |
| Deployed-ingress SSE through real runtime | P12-05 |
| SBOM / immutable digest pin for runtime image | P12-06 |
| Browser E2E / capacity beyond two-domain isolation | P12-07 |
| Live external embedding/LLM provider binding (shim uses deterministic local embed + offline tokenizer on internal net) | P10-05 / follow-on provider packaging |
| Non-production `CE_LIGHTRAG_INPROCESS_SYNTHETIC=true` path | Residual/dev only; not DONE altitude |
