# Frontend Security Boundary

This contract defines the only supported browser-to-service path. It is normative for `M-01`, `M-04`, `M-05`, `M-11`, `C-03`, `C-04`, and `C-05`.

## Boundary and authority

```text
untrusted browser -> public TLS ingress -> Next.js web/BFF -> private FastAPI
                                                      |-> PostgreSQL/object store/providers: forbidden
FastAPI -> PostgreSQL + governed object storage + private adapters/workers
```

- Only the Next.js origin is public. FastAPI, workers, PostgreSQL, object storage, LightRAG, parsers, providers, and runtime controllers are private-network services.
- FastAPI creates the principal and rechecks role, ownership, object state, and domain compatibility. Next middleware redirects for convenience only.
- BFF handlers are streaming reverse proxies and DTO adapters. They do not authorize, persist product state, synthesize identity, or accept a browser-selected upstream.
- Browser-visible IDs are approved opaque product refs. Database IDs classified as private, object keys, paths, URLs, container IDs, provider IDs, and trace IDs never cross this boundary.

## Request path

1. Ingress terminates TLS, normalizes one trusted `Host`, replaces forwarding headers, and routes `/api/v1/*` to Next.
2. Next resolves one server-only `CONTEXT_ENGINE_API_BASE` and validates the ingress-normalized public host and scheme against server configuration; request data can never alter the upstream or select the canonical public origin.
3. The BFF copies only the allowlisted request method, path, query, body, `Accept`, `Content-Type`, browser `Origin`, `Cookie`, `Range`, `If-Range`, `If-Match`, `Idempotency-Key`, `X-CSRF-Token`, and `X-Client-Request-Id`.
4. The BFF removes `Authorization`, `X-API-Key`, all `X-User-*`/`X-Role-*`, caller-supplied `Forwarded`/`X-Forwarded-*`, `Host`, `X-CE-Public-Host`, `X-CE-Public-Proto`, `X-CE-Client-Bucket`, hop-by-hop headers, and content-framing headers it recalculates. Only after the validation in step 2, it adds server-derived `X-CE-Public-Host`, `X-CE-Public-Proto`, and `X-CE-Client-Bucket` values for FastAPI. The client bucket is a bounded opaque ingress classification, never a raw address; browser values can never populate these headers.
5. FastAPI accepts the public host/proto headers only from the private BFF peer, validates them and the forwarded browser `Origin` against the configured public origin, validates its internal upstream `Host`, then checks session, CSRF where required, coarse role, and service-level authorization. It generates `X-Request-ID`; caller values are correlation hints only and never become the server request ID.
6. The BFF passes the upstream body through without buffering. It returns only allowlisted response headers and strips infrastructure headers.

No generic `/proxy?url=` route is permitted.

## Session and CSRF contract

| Item | Rule |
| --- | --- |
| Session cookie | `ce_session`; random opaque value; hash only in PostgreSQL; `HttpOnly`, `Path=/`, no `Domain`, configured `Secure`, validated `SameSite=Lax` or stricter |
| CSRF cookie | `ce_csrf`; signed opaque value using the dedicated CSRF signing key; readable by same-origin browser code, `Path=/`, no `Domain`, same `Secure`/`SameSite` policy; it grants no authentication |
| Bootstrap | `GET /api/v1/auth/csrf` issues a pre-auth CSRF cookie and returns the same value as `{ "csrfToken": "..." }`; response is `no-store` |
| Unsafe request | `POST`, `PUT`, `PATCH`, and `DELETE` require exact cookie/header match in `X-CSRF-Token`, a valid server signature, and an allowed public `Origin` |
| Login | Requires pre-auth CSRF; revokes/rotates the presented session; creates a new session; rotates CSRF to a value bound to that session |
| Logout | Requires authenticated CSRF; revokes the session before expiring both cookies |
| Expiry | `auth_sessions.expires_at` is absolute expiry. Enforce it plus configured idle expiry in FastAPI on every request; initialize `last_used_at` at creation and persist touches no more often than the configured cadence. Streams recheck at bounded checkpoints owned by P7, not per event |

The BFF forwards `Set-Cookie` from FastAPI unchanged except for an explicitly tested development-only `Secure` policy. It never copies a session into JSON, local storage, a bearer token, or a module singleton. `GET /auth/me` is the only identity source after navigation or role change.

Login throttling is keyed by the server-derived ingress client bucket hash plus normalized-username hash in PostgreSQL `login_throttle_buckets`. Failed-login updates lock the unique bucket transactionally; successful authentication clears it. The configured window, failure threshold and block duration are bounded positive values. `429` uses a safe integer `Retry-After`; messages do not disclose whether the account exists or is disabled. Authentication, CSRF, and rate-limit failures use the canonical safe envelope. Raw usernames, addresses/buckets, cookies, CSRF values and passwords are never stored in throttle rows.

CSRF tokens are opaque signed values with a private version, issued-at time, random nonce and binding. Pre-auth tokens bind to a pre-auth sentinel and are rotated after successful login to the new session token hash; authenticated unsafe requests require the session binding. Logout revokes the session before expiring both cookies. Verification accepts only the configured current key; key rotation requires a separately configured bounded previous-key compatibility window and must never reuse the provider-credential encryption key.

## BFF route requirements

| Route class | Required behavior |
| --- | --- |
| JSON | Request-scoped client; body limit; abort propagation; `Cache-Control: private, no-store`; canonical errors |
| Multipart upload | Stream with byte/time limits; do not call `arrayBuffer()`; preserve backpressure and abort; FastAPI performs content validation |
| SSE start/resume | Pass through `text/event-stream` bytes; disable buffering/compression/transformation; propagate disconnect; never infer completion |
| PDF content | Forward `Range`/conditional headers; pass `200`, `206`, or `416`; preserve `Content-Range`, `Accept-Ranges`, safe `ETag`, and content type; no redirect to object storage |

Personalized server fetches use `cache: "no-store"`. Next static rendering, route caches, ISR, CDN caches, and service workers must not cache authenticated JSON, SSE, document bytes, or error bodies. Logging middleware records route templates and safe codes, never cookies, CSRF values, query text, bodies, filenames, excerpts, or content.

## Browser response policy

All application responses set `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and a restrictive `Permissions-Policy`. HTML uses a nonce-based Content Security Policy:

```text
default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none';
script-src 'self' 'nonce-<request-value>'; style-src 'self' 'nonce-<request-value>';
img-src 'self' blob: data:; font-src 'self'; connect-src 'self';
worker-src 'self' blob:; frame-src 'self' blob:; form-action 'self'
```

If the PDF renderer requires a worker/blob exception, add only that source and cover it with a CSP browser test. Do not enable inline script/style broadly. Authenticated PDF/preview bytes use `Cache-Control: private, no-store`, `Content-Disposition: inline`, and a sanitized display filename.

## Authorization and revocation

- Every conversation, event stream, evidence location, document metadata/content, and composer ref query includes the current owner/role predicate in the database query.
- Another user's opaque ID returns the same `404` shape as an unknown ID. Do not distinguish it by timing, body, or headers (`C-04`).
- Admin privileges do not imply access to member conversations or evidence.
- Role/session/source/domain changes take effect on the next request. Long-lived streams recheck session and target eligibility at bounded checkpoints and before terminal persistence.
- Source/domain deletion immediately fences new content reads. Existing viewer blob URLs are revoked client-side on `evidence_unavailable`/redaction and bytes are never served from a shared cache (`M-11`).
- Two users requesting the same document receive independently authorized responses; cache keys are not an authorization control (`C-03`).

## Required negative tests

The deployed-ingress suite must reject: direct public FastAPI access; forged identity/role headers; browser-selected upstreams; missing/wrong Origin; missing/mismatched/replayed CSRF; session fixation; revoked/expired/disabled sessions; cross-owner IDs; member admin access; cached content after logout; object-key/path traversal; over-limit upload; response splitting through filenames; and buffered SSE. Tests must assert that responses, logs, audit rows, traces, and browser storage contain no forbidden values.

Local Studio's explicit middleware order, narrow proxy, and pass-through streaming are candidate patterns only. Context Engine uses cookie sessions, PostgreSQL authorization, CSRF, and private service networking defined here.
