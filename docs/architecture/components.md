# Component Responsibilities

## Backend

| Component | Responsibility |
| --- | --- |
| `app.py` / `context.py` | application factory, lifespan, explicit dependency composition, bootstrap seeds and shutdown |
| `config.py` | environment parsing and fail-fast cookie/runtime settings validation |
| `db.py` / `models.py` | SQLAlchemy engine/session and relational product model |
| `security.py` | password/token/credential cryptography helpers |
| `api/dependencies.py` | database/session injection, current-user and administrator guards |
| `api/errors.py` | canonical safe error envelope |
| `http/middleware.py` | trusted host/origin, request ID/error wrapper, safe logging, body/rate limits, session authentication/CSRF and error mapping |
| `api/routes.py` | thin versioned HTTP/SSE transport and public DTO translation |
| `contracts/` | public DTOs, error envelope, generated OpenAPI snapshot and versioned SSE schemas/fixtures |
| `services/auth.py` | admin seed, login/session lifecycle, role/ownership identity |
| `services/runtime_config.py` | provider credentials, model profiles, parser and synthesis defaults |
| `services/domains.py` | domain lifecycle operations, readiness, leases/generation fencing, deletion |
| `services/sources.py` | upload validation, storage, parser dispatch, canonical blocks/images, delete hooks |
| `services/indexing.py` | LightRAG rendering, submit/poll/retry/cancel, eligibility |
| `services/evidence.py` | scoped query, raw-hit mapping, authorization and safe Evidence projection |
| `services/graphs.py` | authorized read-only domain graph snapshot and label search; opaque ref derivation; admission and safe projection |
| `services/chat_intent.py` | server-owned direct-chat versus domain-seeking intent gate |
| `services/chat_turns.py` | idempotent bounded orchestration, persistence, SSE projection/replay |
| `services/conversations.py` | owner-scoped conversation CRUD and history |
| `services/composer_refs.py` | safe target discovery, opaque tokens, validation and accepted refs |
| `services/prompt_templates.py` / `prompt_assembly.py` | approved templates and private ordered context assembly |
| `services/audit.py` | append-only allowlisted audit writes participating in protected transactions |
| `services/structured_logging.py` | JSON logger with safe field policy |
| `services/health.py` | aggregate liveness/readiness checks with no topology or diagnostic payload |
| `services/lightrag_runtime.py` | private retrieval-runtime client/adaptation boundary, including generation-fenced bounded graph extract/snapshot operations sealed inside the domain runtime |
| `workers/*` | operation claims, heartbeats, cancellation, bounded retry and expired-lease recovery |
| `adapters/domain_runtime_controller.py` | approved local/Docker/command lifecycle controller |

## Frontend

| Component | Responsibility |
| --- | --- |
| `src/middleware.ts` | route-level session guard/redirect behavior |
| `src/state/auth-store.ts` | in-memory current-user/session presentation state |
| `src/lib/api/*` | generated HTTP core plus modular capability clients and canonical safe errors |
| `src/lib/stream/*` | versioned SSE parsing, received/applied cursors, reconnect and canonical live/replay reducer |
| `src/ui/*` | Context Engine-owned fork of approved Local Studio primitives with accessibility contracts |
| `src/app/*` | thin route/layout shells and narrow BFF handlers |
| `src/features/shell/*` | shared application shell and responsive route composition |
| `features/navigation-sidebar/*` | role-aware compact navigation |
| `features/chat-shell/*` | conversation, composer, streamed turn state, citations and Evidence Panel |
| `features/documents/*` | administrator source/domain operations and document inspection |
| `features/graph/*` | read-only Knowledge Domain graph workbench through the approved graph HTTP/DTO contract only |
| `features/settings-panel/*` | backend-owned runtime settings UI |
| `features/user-preferences/*` | non-authoritative local presentation preferences |

## Dependency rules

- Routes may call services; services may call repositories/models and outbound ports; integrations may not bypass service invariants.
- Route dependencies enforce coarse roles; application services re-check ownership, domain eligibility, and mutable state inside the transaction.
- Frontend features call the shared API client, not providers, LightRAG, storage, Docker, controllers, or PostgreSQL. Graph UI may adapt Sigma/Graphology interaction patterns only against the generated graph client; it must not call private runtimes or mutate entities/relations.
- Public DTO mapping strips private IDs and sensitive values at the backend boundary.
- Cross-cutting audit/redaction hooks participate in the same transaction as protected state changes.
- `app` composes features, features may import `ui` and browser-safe `lib`, and `ui` never imports product features or server modules.
- Live and replayed chat events enter one reducer; browser caches and stores are never terminal turn authority.
