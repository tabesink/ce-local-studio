# P10-02 Stack Smoke Inventory

Date: 2026-07-27  
Status: complete for U1 inventory only.  
Plan: `docs/plans/2026-07-27-014-feat-p10-02-stack-smoke-bootstrap-plan.md`  
Authority: `docs/master-build-plan.md` P10-02; `docs/architecture/deployment-topology.md`; DRIFT-08 / DRIFT-15; P10-01 evidence residuals.

## Disposition legend

| Value | Meaning |
| --- | --- |
| `retain` | Already correct; keep |
| `modify` | Change in this slice |
| `add` | New wiring/test/script/doc in this slice |
| `defer-P10-03` | Drain / worker claim recovery runbook |
| `defer-P12` | TLS / deployed ingress denial |
| `residual-browser-csrf` | Browser CSRF product fix (P9-05); not this slice’s exit |

## Chicken-and-egg (blocking)

| Fact | Disposition |
| --- | --- |
| `api` healthcheck hits `/health/ready` | `retain` |
| Ready requires any enabled administrator | `retain` (KTD8) |
| API lifespan must not bootstrap admins (DRIFT-21) | `retain` |
| Compose has `migrate` but **no** `bootstrap` job | `add` (KTD1) |
| Fresh volume → ready never greens → frontend never starts | closed by bootstrap ordering |

## Compose services (`app/compose.stack.yml`)

| Unit | Fact | Disposition |
| --- | --- | --- |
| `postgres` | PG16, health, volume | `retain` |
| `migrate` | `alembic upgrade head`, `restart: "no"` | `retain`; live fresh-volume proof in evidence |
| `bootstrap` | **absent** | `add` — `python -m context_engine.bootstrap_admin`, after migrate, before api |
| `api` | `CE_ADMIN_*` on long-lived env; depends migrate only | `modify` — drop `CE_ADMIN_*`; depend bootstrap completed |
| `worker` | same `CE_ADMIN_*`; depends migrate | `modify` — drop `CE_ADMIN_*`; bootstrap optional |
| `frontend` | `/login` health; depends api healthy | `retain` health; document ≠ trust proof |

## Readiness aggregate (`check_readiness`)

| Check | Fact | Disposition |
| --- | --- | --- |
| DB `SELECT 1` | present | `retain` |
| Exact `SUPPORTED_ALEMBIC_HEAD` | present | `retain` |
| Any enabled administrator | present | `retain` (KTD8) |
| Object-store capability | **absent** (DRIFT-15) | `add` via `object_store_from_root` put+delete (KTD2) |
| Public ready body | `{status:ready}` / safe `503` | `retain` privacy |
| Live process-only | present | `retain` |

## Object store

| Item | Fact | Disposition |
| --- | --- | --- |
| Compose volume `stack-source-storage` → `/data/source-storage` | present | `retain` |
| `object_store_from_root` → `<root>/objects` | product path | `retain` composition for ready probe |
| `ObjectStorage` Protocol readiness method | none | do **not** add |
| S3 Compose service | absent | `defer-P12` / not this slice (KTD6) |

## Smoke altitude

| Item | Fact | Disposition |
| --- | --- | --- |
| `scripts/stack_smoke_live.py` | referenced, **absent** | replace with core smoke doc |
| BFF scripted CSRF→login→SSE | absent | `add` `app/scripts/stack_smoke_core.py` (KTD3–KTD5) |
| Browser UI login CSRF | product gap | `residual-browser-csrf` |
| Worker-leased turn / drain | not required for testing-mode inline | `defer-P10-03` |
| Empty-`CE_*` bypass | boots but not evidence | document non-claim |

## Residuals (non-claims)

| Concern | Owner |
| --- | --- |
| Worker-path smoke / SIGTERM drain (DRIFT-31) | `defer-P10-03` |
| DRIFT-15 worker readiness half | `defer-P10-03` |
| TLS / `testing=false` HTTPS / deployed direct-API denial | `defer-P12` |
| Browser CSRF bootstrap product fix | `residual-browser-csrf` |
| Production / S3 object-store readiness | not Compose filesystem matrix |
| Provider-failure terminal ≠ completed synthesis | named residual in evidence |
| Frontend `/login` 200 alone | not smoke green |

## Proof strategy

| Proof | Owner |
| --- | --- |
| Inventory | U1 |
| Compose bootstrap + admin-secret least-privilege contract tests | U2 |
| Ready store composition unit/PG tests | U3 |
| Live BFF smoke + AE6 negatives | U4 + U5 evidence |
| Tracker / DRIFT half-close | U5 |

## KTDs in force

KTD1 Compose bootstrap before API healthy · KTD2 filesystem store in ready via `object_store_from_root` · KTD3 sealed SSE green bar · KTD4 scripted BFF · KTD5 F4 negatives required · KTD6 no S3/LightRAG overlay · KTD7 verify stays config-level · KTD8 any-enabled-admin · KTD9 bootstrap-only `CE_ADMIN_*`.
