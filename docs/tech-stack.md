# Technology Inventory

## Runtime stack

| Layer | Technology | Reviewed version/constraint | Purpose |
| --- | --- | --- | --- |
| Backend language | Python | `>=3.12` | API, services, workers, integrations |
| API | FastAPI | `>=0.111.0` | Versioned REST and SSE endpoints |
| ASGI | Uvicorn standard | `>=0.30.0` | Production/dev server |
| ORM | SQLAlchemy | `>=2.0.30` | Declarative models and transactions |
| Migrations | Alembic | `>=1.13.2` | Phase 1 managed migrations; deferred-feature revisions in reviewed HEAD are not ported |
| Database | PostgreSQL | 16 in Compose | Durable relational authority |
| PostgreSQL driver | psycopg binary | `>=3.2.0` | SQLAlchemy connectivity |
| Password hashing | argon2-cffi | `>=23.1.0` | User password verification |
| Secret encryption | cryptography | `>=42.0.0` | Fernet-style provider credential encryption |
| Frontend | Next.js App Router | `16.2.10` | Thin server/client web application |
| UI runtime | React / React DOM | `19.2.7` | Component rendering |
| Language | TypeScript | `5.9.3` | Typed browser/server UI code |
| Styling | Tailwind CSS | `4.1.18` | Token-driven compact workstation UI |
| CSS integration | `@tailwindcss/postcss` | `4.1.18` | Next.js style build |
| Icons | lucide-react | `0.561.0` | Shared icon vocabulary |

P0-01 preserved `app/pyproject.toml`, `app/uv.lock`, the frontend package metadata and lockfile, and aligned package/launch paths on `app/context_engine` and `app/client`. These artifacts establish the canonical pinned dependency inputs; the current local root gate passes, but that does not prove its still-missing contract, PostgreSQL, privacy, browser, or deployed-ingress coverage or production readiness.

The reviewed lock resolves FastAPI 0.139.0, Uvicorn 0.50.2, SQLAlchemy 2.0.51, Alembic 1.18.5, argon2-cffi 25.1.0, cryptography 49.0.0, and psycopg 3.3.4. Optional RAG versions include NumPy 2.5.1, json-repair 0.61.2, python-dotenv 1.2.2, NetworkX 3.6.1, nano-vectordb 0.0.4.3, and tiktoken 0.13.0. Vendored LightRAG is asserted at 1.4.16.

## LightRAG and AI integration

- Editable vendored runtime package at `app/vendor/lightrag`, treated as a private adapter dependency rather than public product authority.
- Optional Python dependencies: NumPy, json-repair, python-dotenv, NetworkX, nano-vectordb, and tiktoken.
- One private LightRAG runtime per Knowledge Domain.
- Supported model providers: OpenAI, AWS Bedrock, and Ollama.
- Supported document parsers: local Docling and external Reducto.
- Browser code never invokes these systems directly; backend adapters inject typed secrets/config and map outputs to product-owned records.

## Application structure

Production structure evaluates Local Studio's separation of thin route shells, feature modules, shared browser-safe API clients, UI primitives, explicit backend dependency composition, and root structural gates as candidate patterns requiring Context Engine-native verification. It does not adopt the Bun controller, SQLite stores, Pi agent runtime, plugin system, or renderer filesystem access. See `architecture/production-adaptation-blueprint.md`.

```text
app/
  context_engine/      canonical FastAPI package: routes, services, models, worker and adapters
  client/              lifted Next.js App Router application and frontend tests
  vendor/lightrag/     vendored retrieval runtime behind the CE adapter boundary
  compose.stack.yml    P0-aligned stack definition; P10 owns production-like runtime proof
  Dockerfile           P0-aligned backend image definition; P10 owns full-stack proof
  pyproject.toml        canonical Python manifest paired with app/uv.lock
scripts/dev.sh          P0-aligned development entry for app/ and app/client/
docs/                   target product, contract, architecture and quality authority
```

The target remains a modular monolith. P0-01 selected `app/context_engine/` as the canonical backend package because all product imports, package discovery, Uvicorn, Docker, Compose, and Alembic assumptions already used `context_engine`; the former lifted `app/server/` path is retired. `app/migrations/` remains the canonical migration location, with its baseline owned by P1.

## Delivery and local runtime

- Multi-stage responsibility expressed as Compose services: `postgres`, one-shot `migrate`, `api`, and `frontend`.
- Backend image: `python:3.12-slim`; frontend uses its own Dockerfile and listens on port 3000.
- Frontend image is a Node 22 Alpine multi-stage build.
- API listens on 8000; Compose publishes both services only to `127.0.0.1` by default.
- Health checks: `/health/live`, `/health/ready`, and frontend `/login`.
- Compose uses local controller/LightRAG adapters for the runnable P10 stack; production may substitute the approved server-only Docker controller boundary.
- Persistent PostgreSQL named volume; source and per-domain runtime roots are backend-managed filesystem locations.

## Configuration surface

Required/bootstrap variables include:

- `CONTEXT_ENGINE_DATABASE_URL`
- `CE_ADMIN_USERNAME`, `CE_ADMIN_PASSWORD`
- `CONFIG_ENCRYPTION_KEY`
- `CE_SESSION_COOKIE_SECURE`, `CE_SESSION_COOKIE_SAMESITE`, `CE_SESSION_TTL_SECONDS`
- `CE_DOMAIN_RUNTIME_ROOT`, `CE_DOMAIN_RUNTIME_CONTROLLER_KIND`, `CE_DOMAIN_CONTROLLER_COMMAND`, controller timeout
- worker IDs and lease durations for domain deletion, source preparation, and indexing
- `CE_SOURCE_STORAGE_ROOT`, `CE_LIGHTRAG_CLIENT_KIND`
- `CONTEXT_ENGINE_API_BASE` for server-side frontend proxy/rewrites
- Compose PostgreSQL credentials and published port overrides

Secrets must be supplied by the deployment environment and never committed or exposed to the frontend bundle.

## Testing and quality tools

The root quality command is a release contract: pinned install, backend lint/type/test, frontend lint/type/build/test, dependency and cycle checks, OpenAPI/SSE snapshot parity, Alembic fresh/upgrade/downgrade tests, privacy scans, and deployed-path integration. Browser E2E must cover login, domain/source administration, streamed chat/reconnect/evidence, governed context, redaction, and safe failure states.

- Pytest `>=8.2.0` with HTTPX `>=0.27.0` and Ruff `>=0.5.0`.
- Backend suites cover auth, runtime config, domain lifecycle/controllers, sources, indexing, retrieval, conversations/chat, governed context, operational safety, and Docker integration.
- Versioned OpenAPI snapshots (`F-001` through `F-008` and `F-012`) detect contract drift.
- Frontend uses Node's built-in test runner for foundation and chat behavior plus TypeScript `--noEmit` and Next production builds.
- `scripts/verify.sh` and `.github/workflows/verify.yml` provide the P0 root verification skeleton from pinned current-tree inputs. The current local checks pass after adding focused backend coverage and repairing inherited frontend type/build/test drift. HTTP catalog/response-model parity, canonical SSE schemas/fixtures, PostgreSQL/migration, privacy, browser, and deployed-ingress gates remain absent, so this is not B0 or release evidence.
- `scripts/generate_openapi.py`, `app/contracts/openapi.json`, and the generated TypeScript artifact start P0-06 from registered FastAPI routes. The root gate now regenerates and byte-compares OpenAPI and TypeScript and rejects stale fixtures; production and generation share route registration; health responses use closed generated components; and the closed/bounded login request is pinned through the registered operation to the generated browser capability call. The registered/catalog route delta and identity response drift remain recorded in `docs/_scratch/p0-06-generated-contract-inventory.md`; most response DTOs remain handwritten, and canonical SSE schema/fixture generation is not yet implemented.
- The current workflow and runtime image both pin Python 3.12. A later compatibility version may be added explicitly, but must not replace deployment-version coverage.

## Rebuild cautions

- Do not replace leased database-backed work with Redis/Celery without a product decision.
- Do not turn vendored LightRAG internals into public product contracts.
- SQLite support in `db.py` is a test convenience; PostgreSQL is the deployment source of truth.
- Next.js, React, and other exact versions are future-dated in this snapshot; restore from the committed lockfiles for reproducibility.
- Current Compose selects local controller and local LightRAG clients. It proves packaging and API/UI wiring, not real Docker/provider/parser/RAG production execution.
