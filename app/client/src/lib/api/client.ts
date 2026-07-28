import { ApiError, normalizeApiError } from "@/lib/api/errors";
import { isUnsafeHttpMethod, resolveCsrfToken, refreshCsrfToken } from "@/lib/api/csrf";

type UnauthorizedHandler = (() => void) | null;

type RequestOptions = RequestInit & {
  handleUnauthorized?: boolean;
  /** When true, skip CSRF attach (used only for CSRF bootstrap itself). */
  skipCsrf?: boolean;
};

export type CeFetchResult<T> = {
  body: T;
  etag: string | null;
};

const API_PREFIX = "/api/v1";
let unauthorizedHandler: UnauthorizedHandler = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler) {
  unauthorizedHandler = handler;
}

export {
  ifMatchHeader,
  idempotencyKeyHeader,
  readCsrfTokenFromCookie,
  resolveCsrfToken,
  refreshCsrfToken,
} from "@/lib/api/csrf";

async function attachCsrf(headers: Headers, method: string | undefined, skipCsrf?: boolean): Promise<void> {
  if (skipCsrf || !isUnsafeHttpMethod(method) || headers.has("X-CSRF-Token")) return;
  const token = await resolveCsrfToken();
  if (token) headers.set("X-CSRF-Token", token);
}

async function executeFetch(url: string, options: RequestOptions): Promise<Response> {
  const headers = new Headers(options.headers);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  if (options.body && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  await attachCsrf(headers, options.method, options.skipCsrf);

  try {
    return await fetch(url, {
      ...options,
      credentials: "include",
      headers,
    });
  } catch {
    throw new ApiError({
      status: 0,
      code: "network_error",
      message: "Context Engine API is unavailable.",
      requestId: null,
      fields: {},
    });
  }
}

export async function ceFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const result = await ceFetchWithMeta<T>(path, options);
  return result.body;
}

/** Feature-owned helper when callers need response ETag alongside JSON body. */
export async function ceFetchWithMeta<T>(path: string, options: RequestOptions = {}): Promise<CeFetchResult<T>> {
  const url = contextEngineApiPath(path);
  let response = await executeFetch(url, options);

  if (!response.ok) {
    const firstBody = await readSafeJson(response);
    const firstError = normalizeApiError(response.status, firstBody);
    if (
      firstError.code === "csrf_invalid" &&
      isUnsafeHttpMethod(options.method) &&
      !options.skipCsrf
    ) {
      const token = await refreshCsrfToken();
      if (token) {
        const headers = new Headers(options.headers);
        headers.set("X-CSRF-Token", token);
        response = await executeFetch(url, { ...options, headers, skipCsrf: true });
      } else {
        if (response.status === 401 && options.handleUnauthorized !== false) {
          unauthorizedHandler?.();
        }
        throw firstError;
      }
    } else {
      if (response.status === 401 && options.handleUnauthorized !== false) {
        unauthorizedHandler?.();
      }
      throw firstError;
    }
  }

  const etag = response.headers.get("etag");

  if (response.status === 204) {
    return { body: undefined as T, etag };
  }

  // Success path after optional CSRF retry still needs body parse when we already threw on first failure.
  // If we retried, response is a fresh success/error Response.
  if (!response.ok) {
    const body = await readSafeJson(response);
    const error = normalizeApiError(response.status, body);
    if (response.status === 401 && options.handleUnauthorized !== false) {
      unauthorizedHandler?.();
    }
    throw error;
  }

  if (response.status === 204) {
    return { body: undefined as T, etag };
  }

  const body = await readSafeJson(response);
  return { body: body as T, etag };
}

/** Cookie-authenticated binary/text body fetch for preview surfaces (not JSON-only). */
export async function ceFetchBlob(path: string, options: RequestOptions = {}): Promise<{ blob: Blob; contentType: string }> {
  const url = contextEngineApiPath(path);
  const headers = new Headers(options.headers);
  if (!headers.has("Accept")) headers.set("Accept", "*/*");
  await attachCsrf(headers, options.method, options.skipCsrf);

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      credentials: "include",
      headers,
    });
  } catch {
    throw new ApiError({
      status: 0,
      code: "network_error",
      message: "Context Engine API is unavailable.",
      requestId: null,
      fields: {},
    });
  }

  if (!response.ok) {
    const body = await readSafeJson(response);
    const error = normalizeApiError(response.status, body);
    if (error.code === "csrf_invalid" && isUnsafeHttpMethod(options.method) && !options.skipCsrf) {
      const token = await refreshCsrfToken();
      if (token) {
        headers.set("X-CSRF-Token", token);
        return ceFetchBlob(path, { ...options, headers, skipCsrf: true });
      }
    }
    if (response.status === 401 && options.handleUnauthorized !== false) {
      unauthorizedHandler?.();
    }
    throw error;
  }

  const contentType = (response.headers.get("content-type") ?? "application/octet-stream").split(";", 1)[0].trim();
  const blob = await response.blob();
  return { blob, contentType };
}

export function contextEngineApiPath(path: string): string {
  const trimmed = path.trim();
  if (/^https?:\/\//i.test(trimmed) || trimmed.startsWith("//")) {
    throw new ApiError({
      status: 0,
      code: "invalid_api_path",
      message: "Invalid API path.",
      requestId: null,
      fields: {},
    });
  }

  const normalized = trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
  return normalized.startsWith(API_PREFIX) ? normalized : `${API_PREFIX}${normalized}`;
}

async function readSafeJson(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) return null;
  try {
    return await response.json();
  } catch {
    return null;
  }
}
