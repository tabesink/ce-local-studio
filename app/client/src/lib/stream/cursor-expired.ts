import { ApiError, isApiError } from "../api/errors.ts";
import type { components } from "../api/generated/openapi.ts";

export type TerminalSnapshotDto = components["schemas"]["TerminalSnapshotDto"];

export function isCursorExpiredError(error: unknown): boolean {
  if (!isApiError(error)) return false;
  return error.status === 410 || error.code === "cursor_expired";
}

/** Extract `terminalSnapshot` from a raw `{ error, terminalSnapshot? }` JSON body. */
export function extractTerminalSnapshot(body: unknown): unknown | undefined {
  if (!body || typeof body !== "object" || !("terminalSnapshot" in body)) return undefined;
  return (body as { terminalSnapshot?: unknown }).terminalSnapshot;
}

export function getTerminalSnapshotFromError(error: unknown): unknown | undefined {
  if (!error || typeof error !== "object" || !("terminalSnapshot" in error)) return undefined;
  return (error as { terminalSnapshot?: unknown }).terminalSnapshot;
}

export function isTerminalSnapshotDto(value: unknown): value is TerminalSnapshotDto {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const source = value as {
    turnId?: unknown;
    status?: unknown;
    evidence?: unknown;
    citations?: unknown;
  };
  return (
    typeof source.turnId === "string" &&
    typeof source.status === "string" &&
    Array.isArray(source.evidence) &&
    Array.isArray(source.citations)
  );
}

export type ApiErrorWithTerminalSnapshot = ApiError & { terminalSnapshot?: unknown };

export function attachTerminalSnapshot(
  error: ApiError,
  body: unknown,
): ApiErrorWithTerminalSnapshot {
  const snapshot = extractTerminalSnapshot(body);
  if (snapshot !== undefined) {
    (error as ApiErrorWithTerminalSnapshot).terminalSnapshot = snapshot;
  }
  return error as ApiErrorWithTerminalSnapshot;
}
