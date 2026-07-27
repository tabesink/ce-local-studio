import { createHash } from "node:crypto";

export type BffProxyConfig = {
  apiBase: URL;
  publicOrigin: URL;
  /** Test-only injectable opaque bucket; production derives via `deriveClientBucket`. */
  clientBucket?: string;
};

type FetchImplementation = (input: string | URL | Request, init?: RequestInit) => Promise<Response>;
type StreamingRequestInit = RequestInit & { duplex?: "half" };

/** Exclusive allowlist from docs/architecture/frontend-security-boundary.md step 3 (plus Origin copied separately). */
const REQUEST_HEADERS = [
  "accept",
  "content-type",
  "cookie",
  "if-match",
  "if-range",
  "idempotency-key",
  "range",
  "x-client-request-id",
  "x-csrf-token",
] as const;

const RESPONSE_HEADERS = [
  "accept-ranges",
  "content-disposition",
  "content-length",
  "content-range",
  "content-type",
  "etag",
  "retry-after",
  "x-accel-buffering",
  "x-content-type-options",
  "x-request-id",
] as const;

const PUBLIC_HOST_HEADER = "X-CE-Public-Host";
const PUBLIC_PROTO_HEADER = "X-CE-Public-Proto";
const CLIENT_BUCKET_HEADER = "X-CE-Client-Bucket";

function trustedUrl(value: string, label: string): URL {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error(`${label} is invalid.`);
  }
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) {
    throw new Error(`${label} is invalid.`);
  }
  return url;
}

export function resolveBffProxyConfig(env: NodeJS.ProcessEnv = process.env): BffProxyConfig {
  const apiBase = trustedUrl(env.CONTEXT_ENGINE_API_BASE ?? "http://127.0.0.1:8000", "API base");
  const configuredOrigin = env.CONTEXT_ENGINE_PUBLIC_ORIGIN;
  if (!configuredOrigin && env.NODE_ENV === "production") {
    throw new Error("Public origin is required in production.");
  }
  const publicOrigin = trustedUrl(configuredOrigin ?? "http://127.0.0.1:3000", "Public origin");
  if (publicOrigin.pathname !== "/" || publicOrigin.search || publicOrigin.hash) {
    throw new Error("Public origin must not include a path, query, or fragment.");
  }
  return { apiBase, publicOrigin };
}

/**
 * Opaque ingress classification for FastAPI (1–128 chars).
 * Local recipe: SHA-256 hex (32 chars) of a bounded connection hint — never emit a raw address.
 * P10 owns hardened ingress classification; unit tests may inject `config.clientBucket`.
 */
export function deriveClientBucket(request: Request, config: BffProxyConfig): string {
  if (config.clientBucket) {
    const injected = config.clientBucket.trim();
    if (!(1 <= injected.length && injected.length <= 128)) {
      throw new Error("Client bucket override must be 1–128 characters.");
    }
    return injected;
  }
  const forwarded = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  const realIp = request.headers.get("x-real-ip")?.trim();
  const hint = forwarded || realIp || "unknown";
  return createHash("sha256").update(`ce-client-bucket|${hint}`).digest("hex").slice(0, 32);
}

function upstreamUrl(request: Request, path: readonly string[], apiBase: URL): URL {
  if (path.length === 0 || path.some((segment) => !segment || segment === "." || segment === ".." || segment.includes("/"))) {
    throw new Error("API path is invalid.");
  }
  const target = new URL(`/api/v1/${path.map(encodeURIComponent).join("/")}`, apiBase);
  target.search = new URL(request.url).search;
  return target;
}

function upstreamHeaders(request: Request, config: BffProxyConfig): Headers {
  const headers = new Headers();
  for (const name of REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  const browserOrigin = request.headers.get("origin");
  if (browserOrigin !== null) headers.set("origin", browserOrigin);

  // Never forward caller-supplied trust headers (allowlist rebuild already omits them).
  headers.set(PUBLIC_HOST_HEADER, config.publicOrigin.host);
  headers.set(PUBLIC_PROTO_HEADER, config.publicOrigin.protocol.replace(/:$/, ""));
  headers.set(CLIENT_BUCKET_HEADER, deriveClientBucket(request, config));
  return headers;
}

function browserHeaders(upstream: Response): Headers {
  const headers = new Headers();
  for (const name of RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  const getSetCookie = (
    upstream.headers as Headers & { getSetCookie?: () => string[] }
  ).getSetCookie?.bind(upstream.headers);
  if (typeof getSetCookie === "function") {
    for (const cookie of getSetCookie()) {
      headers.append("set-cookie", cookie);
    }
  } else {
    const single = upstream.headers.get("set-cookie");
    if (single !== null) headers.append("set-cookie", single);
  }
  headers.set("cache-control", "private, no-store, no-transform");
  return headers;
}

export async function proxyContextEngineRequest(
  request: Request,
  path: readonly string[],
  config: BffProxyConfig,
  fetchImplementation: FetchImplementation = fetch,
): Promise<Response> {
  const method = request.method.toUpperCase();
  const init: StreamingRequestInit = {
    method,
    headers: upstreamHeaders(request, config),
    redirect: "manual",
    signal: request.signal,
  };
  if (method !== "GET" && method !== "HEAD") {
    init.body = request.body;
    init.duplex = "half";
  }
  const upstream = await fetchImplementation(upstreamUrl(request, path, config.apiBase), init);
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: browserHeaders(upstream),
  });
}
