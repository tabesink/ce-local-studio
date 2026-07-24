export type SseEvent = { id: string; event: string; data: Record<string, unknown> };

export class InvalidSseEventError extends Error {
  readonly code = "invalid_sse_event";
  constructor(message = "Stream response was invalid.") {
    super(message);
    this.name = "InvalidSseEventError";
  }
}

function parseSseBlock(block: string): SseEvent | null {
  let id = "";
  let event = "";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (!line || line.startsWith(":")) continue;
    if (line.startsWith("id:")) id = line.slice(3).trimStart();
    if (line.startsWith("event:")) event = line.slice(6).trimStart();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (!id && !event && dataLines.length === 0) return null;
  if (!id || !event || dataLines.length !== 1) throw new InvalidSseEventError();
  try {
    const data: unknown = JSON.parse(dataLines[0]);
    if (!data || typeof data !== "object" || Array.isArray(data)) throw new InvalidSseEventError();
    return { id, event, data: data as Record<string, unknown> };
  } catch (error) {
    if (error instanceof InvalidSseEventError) throw error;
    throw new InvalidSseEventError();
  }
}

export class SseParser {
  private buffer = "";

  push(text: string): SseEvent[] {
    this.buffer += text.replaceAll("\r\n", "\n");
    const events: SseEvent[] = [];
    let boundary = this.buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const block = this.buffer.slice(0, boundary);
      this.buffer = this.buffer.slice(boundary + 2);
      const parsed = parseSseBlock(block);
      if (parsed) events.push(parsed);
      boundary = this.buffer.indexOf("\n\n");
    }
    return events;
  }

  finish(): void {
    if (this.buffer.trim()) throw new InvalidSseEventError("Stream response ended mid-frame.");
  }
}
