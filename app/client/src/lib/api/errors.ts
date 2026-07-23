export type ApiErrorOptions = {
  status: number;
  code: string;
  message: string;
  requestId: string | null;
  fields: Record<string, string>;
};

export class ApiError extends Error {
  status: number;
  code: string;
  requestId: string | null;
  fields: Record<string, string>;

  constructor(options: ApiErrorOptions) {
    super(options.message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.requestId = options.requestId;
    this.fields = options.fields;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function normalizeApiError(status: number, body: unknown): ApiError {
  const envelope = readErrorEnvelope(body);
  if (envelope) {
    return new ApiError({
      status,
      code: envelope.code,
      message: envelope.message,
      requestId: envelope.requestId,
      fields: envelope.fields,
    });
  }

  return new ApiError({
    status,
    code: status === 403 ? "forbidden" : status === 401 ? "unauthenticated" : "http_error",
    message: status === 403 ? "Forbidden." : status === 401 ? "Authentication required." : "Request failed.",
    requestId: null,
    fields: {},
  });
}

function readErrorEnvelope(body: unknown): ApiErrorOptions | null {
  if (!body || typeof body !== "object" || !("error" in body)) return null;
  const error = (body as { error?: unknown }).error;
  if (!error || typeof error !== "object") return null;

  const source = error as {
    code?: unknown;
    message?: unknown;
    requestId?: unknown;
    fields?: unknown;
  };
  if (typeof source.code !== "string" || typeof source.message !== "string") return null;

  return {
    status: 0,
    code: source.code,
    message: source.message,
    requestId: typeof source.requestId === "string" ? source.requestId : null,
    fields: readFields(source.fields),
  };
}

function readFields(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return Object.fromEntries(
    Object.entries(value).flatMap(([field, message]) =>
      typeof message === "string" ? [[field, message]] : [],
    ),
  );
}
