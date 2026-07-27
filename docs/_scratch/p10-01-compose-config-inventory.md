# P10-01 Compose Config Inventory

Date: 2026-07-27  
Status: complete for U1 inventory only.  
Plan: `docs/plans/2026-07-27-013-feat-p10-01-compose-production-like-config-plan.md`  
Authority: `docs/master-build-plan.md` P10-01; `docs/architecture/deployment-topology.md`; `docs/architecture/frontend-security-boundary.md`; DRIFT-08.

## Disposition legend

| Value | Meaning |
| --- | --- |
| `retain` | Already correct; keep |
| `modify` | Change in this slice |
| `add` | New wiring/test/doc in this slice |
| `defer-P10-02` | Smoke / bootstrap / storage readiness |
| `defer-P10-03` | Drain / operator runbook |
| `defer-P12` | TLS / deployed ingress denial |

## Compose services (`app/compose.stack.yml`)

| Unit | Fact | Disposition |
| --- | --- | --- |
| `postgres` | PostgreSQL 16, loopback publish, healthcheck, volume | `retain` |
| `migrate` | `alembic upgrade head`, `restart: "no"`, `service_completed_successfully` | `retain` role; unblocked by image `modify` |
| `api` | uvicorn factory, filesystem volumes, local LightRAG/controller, empty CE_* defaults, `CONTEXT_ENGINE_TESTING:-true` | `modify` ingress-wired example + optional CE_*; pin stack network |
| `worker` | same env posture as api; heartbeat healthcheck | `modify` (mirror api ingress) |
| `frontend` | `CONTEXT_ENGINE_API_BASE=http://api:8000`; **no** `CONTEXT_ENGINE_PUBLIC_ORIGIN`; `NODE_ENV=production` in image | `modify` + static IP for peer allowlist |

## Docker / image

| Path | Fact | Disposition |
| --- | --- | --- |
| `app/Dockerfile` | Copies package + vendor; **does not COPY `migrations/`** | `modify` |
| `app/.dockerignore` | Does not exclude `migrations/` | `retain` |
| `app/client/Dockerfile` | Production runner; API base default; no public origin | `retain` (runtime env from compose) |
| `compose.stack.live.yml` | Referenced in comments; **absent** | `defer-P10-02` / later fidelity (out of P10-01) |

## Env contract

| Item | Fact | Disposition |
| --- | --- | --- |
| `.env.stack.example` | Documents testing bypass as default; CE_* commented | `modify` — primary = ingress-wired HTTP (`testing=true` + full CE_*); bypass secondary |
| Dual origin | FastAPI `CE_PUBLIC_ORIGIN` vs BFF `CONTEXT_ENGINE_PUBLIC_ORIGIN` | `add` shared `CE_STACK_PUBLIC_ORIGIN` feeding both in compose |
| Peers | Empty / host-loopback insufficient for BFF container source IP | `modify` — pinned `ce_stack` subnet + frontend `172.30.55.10/32` |
| Cookie Secure | Example `false` for HTTP | `retain` for primary HTTP profile |
| CSRF vs encryption key | Guidance present; not contract-tested | `add` example distinct placeholders + test |
| `.env.stack.local` | Local secrets (gitignored) | operator recreate from example (not committed) |

## Trust / residual ownership

| Concern | Disposition |
| --- | --- |
| Login/CSRF/SSE smoke | `defer-P10-02` |
| Admin bootstrap Compose job | `defer-P10-02` |
| Object-store readiness (DRIFT-15) | `defer-P10-02` |
| Worker SIGTERM drain (DRIFT-31) | `defer-P10-03` |
| TLS / `testing=false` HTTPS / direct-API denial | `defer-P12` |
| Frontend healthcheck ≠ BFF trust proof | document in evidence; smoke `defer-P10-02` |

## Peer CIDR strategy (chosen for U3)

Prefer **pinned Compose network** `172.30.55.0/24` with frontend static `172.30.55.10` and `CE_TRUSTED_BFF_PEERS=172.30.55.10/32`. Reject broad `172.16.0.0/12` as primary (host→published API via bridge gateway must not look trusted). Inventory records gateway `172.30.55.1` as outside the peer allowlist.

## Proof strategy

| Proof | Owner |
| --- | --- |
| Dockerfile + compose/env contract tests | P10-01 |
| `compose config --quiet` with verify placeholders | P10-01 |
| Backend image build includes migrations | P10-01 evidence |
| Live BFF→API CSRF / login smoke | P10-02 |
