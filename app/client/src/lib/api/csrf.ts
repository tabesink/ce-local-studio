/** Transient same-origin CSRF accessor. Never persist the token. */

const CSRF_COOKIE = "ce_csrf";

export function readCsrfTokenFromCookie(): string | null {
  if (typeof document === "undefined") return null;
  const parts = document.cookie.split("; ");
  for (const part of parts) {
    const eq = part.indexOf("=");
    if (eq <= 0) continue;
    const name = part.slice(0, eq);
    if (name !== CSRF_COOKIE) continue;
    const raw = part.slice(eq + 1);
    try {
      return decodeURIComponent(raw);
    } catch {
      return raw;
    }
  }
  return null;
}

/** Bootstrap or refresh CSRF via GET /api/v1/auth/csrf; returns cookie/body token. */
export async function refreshCsrfToken(fetchImpl: typeof fetch = fetch): Promise<string | null> {
  const response = await fetchImpl("/api/v1/auth/csrf", {
    method: "GET",
    credentials: "include",
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) return readCsrfTokenFromCookie();
  try {
    const body = (await response.json()) as { csrfToken?: unknown };
    if (typeof body.csrfToken === "string" && body.csrfToken.length > 0) {
      return body.csrfToken;
    }
  } catch {
    /* fall through to cookie */
  }
  return readCsrfTokenFromCookie();
}

export async function resolveCsrfToken(fetchImpl: typeof fetch = fetch): Promise<string | null> {
  return readCsrfTokenFromCookie() ?? refreshCsrfToken(fetchImpl);
}

export function isUnsafeHttpMethod(method: string | undefined): boolean {
  const normalized = (method ?? "GET").toUpperCase();
  return normalized === "POST" || normalized === "PUT" || normalized === "PATCH" || normalized === "DELETE";
}

export function ifMatchHeader(version: number | string | null | undefined): Record<string, string> | undefined {
  if (version == null || version === "") return undefined;
  return { "If-Match": `"${version}"` };
}

export function idempotencyKeyHeader(key: string | null | undefined): Record<string, string> | undefined {
  if (key == null || key === "") return undefined;
  return { "Idempotency-Key": key };
}
