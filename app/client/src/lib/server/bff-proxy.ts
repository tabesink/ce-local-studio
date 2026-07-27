export type BffProxyConfig = {
  apiBase: URL;
  publicOrigin: URL;
};

type FetchImplementation = (input: string | URL | Request, init?: RequestInit) => Promise<Response>;
type StreamingRequestInit = RequestInit & { duplex?: "half" };

const REQUEST_HEADERS = [
  "accept",
  "accept-language",
  "content-type",
  "cookie",
  "if-match",
  "if-none-match",
  "if-range",
  "range",
  "x-csrf-token",
  "x-request-id",
] as const;
const RESPONSE_HEADERS = [
  "accept-ranges",
  "content-disposition",
  "content-length",
  "content-range",
  "content-type",
  "etag",
  "retry-after",
  "set-cookie",
  "x-accel-buffering",
  "x-content-type-options",
  "x-request-id",
] as const;

function trustedUrl(value: string, label: string): URL {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error(`${label} is invalid.`);
  }
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) {
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

function upstreamUrl(request: Request, path: readonly string[], apiBase: URL): URL {
  if (path.length === 0 || path.some((segment) => !segment || segment === "." || segment === ".." || segment.includes("/"))) {
    throw new Error("API path is invalid.");
  }
  const target = new URL(`/api/v1/${path.map(encodeURIComponent).join("/")}`, apiBase);
  target.search = new URL(request.url).search;
  return target;
}

function upstreamHeaders(request: Request, publicOrigin: URL): Headers {
  const headers = new Headers();
  for (const name of REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  headers.set("origin", publicOrigin.origin);
  headers.set("x-forwarded-host", publicOrigin.host);
  headers.set("x-forwarded-proto", publicOrigin.protocol.slice(0, -1));
  return headers;
}

function browserHeaders(upstream: Response): Headers {
  const headers = new Headers();
  for (const name of RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value !== null) headers.set(name, value);
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
    headers: upstreamHeaders(request, config.publicOrigin),
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
