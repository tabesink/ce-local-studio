import { ApiError, normalizeApiError } from "@/lib/api/errors";
import { contextEngineApiPath } from "@/lib/api/client";

export type SseEvent = {
  event: string;
  payload: Record<string, unknown>;
};

export async function postSse(
  path: string,
  body: unknown,
  onEvent: (event: SseEvent) => void,
): Promise<void> {
  const response = await fetch(contextEngineApiPath(path), {
    method: "POST",
    credentials: "include",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const contentType = response.headers.get("content-type") ?? "";
    const payload = contentType.includes("application/json") ? await response.json().catch(() => null) : null;
    throw normalizeApiError(response.status, payload);
  }

  const text = await response.text();
  for (const block of text.trim().split("\n\n")) {
    if (!block) continue;
    const parsed = parseSseBlock(block);
    if (parsed) onEvent(parsed);
  }
}

function parseSseBlock(block: string): SseEvent | null {
  let event = "";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event: ")) event = line.slice("event: ".length);
    if (line.startsWith("data: ")) data = line.slice("data: ".length);
  }
  if (!event || !data) return null;
  try {
    const payload = JSON.parse(data);
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) return null;
    return { event, payload: payload as Record<string, unknown> };
  } catch {
    throw new ApiError({
      status: 0,
      code: "invalid_sse_event",
      message: "Stream response was invalid.",
      requestId: null,
      fields: {},
    });
  }
}
