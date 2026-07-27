import { ApiError, normalizeApiError } from "@/lib/api/errors";
import { contextEngineApiPath } from "@/lib/api/client";
import { attachTerminalSnapshot } from "@/lib/stream/cursor-expired";
import { InvalidSseEventError, SseParser, type SseEvent } from "@/lib/stream/sse-parser";

export type { SseEvent } from "@/lib/stream/sse-parser";

function invalidStream(error: InvalidSseEventError): ApiError {
  return new ApiError({ status: 0, code: error.code, message: error.message, requestId: null, fields: {} });
}

async function consumeSse(response: Response, onEvent: (event: SseEvent) => void): Promise<void> {
  if (!response.body) throw invalidStream(new InvalidSseEventError("Stream response was unavailable."));
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();
  try {
    while (true) {
      const { value, done } = await reader.read();
      for (const event of parser.push(decoder.decode(value, { stream: !done }))) onEvent(event);
      if (done) break;
    }
    parser.finish();
  } catch (error) {
    if (error instanceof InvalidSseEventError) throw invalidStream(error);
    throw error;
  }
}

async function openSse(path: string, init: RequestInit, onEvent: (event: SseEvent) => void): Promise<void> {
  const response = await fetch(contextEngineApiPath(path), {
    ...init,
    credentials: "include",
    headers: { Accept: "text/event-stream", ...init.headers },
  });
  if (!response.ok) {
    const contentType = response.headers.get("content-type") ?? "";
    const payload = contentType.includes("application/json") ? await response.json().catch(() => null) : null;
    const error = attachTerminalSnapshot(
      normalizeApiError(response.status, payload),
      payload,
    ) as ApiError & { retryAfterMs?: number; terminalSnapshot?: unknown };
    const retryAfter = response.headers.get("retry-after");
    if (retryAfter) {
      const seconds = Number(retryAfter);
      const dateDelay = Date.parse(retryAfter) - Date.now();
      error.retryAfterMs = Number.isFinite(seconds) ? Math.max(0, seconds * 1000) : Math.max(0, dateDelay);
    }
    throw error;
  }
  await consumeSse(response, onEvent);
}

export async function getSse(path: string, onEvent: (event: SseEvent) => void): Promise<void> {
  await openSse(path, { method: "GET" }, onEvent);
}
export async function postSse(path: string, body: unknown, onEvent: (event: SseEvent) => void): Promise<void> {
  await openSse(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }, onEvent);
}
