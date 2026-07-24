export type StreamTransportState = "connected" | "reconnecting" | "offline";

export type StreamCursorSnapshot = {
  receivedSequence: number;
  appliedSequence: number;
  turnId: string | null;
  terminal: boolean;
};

type ReconnectOptions = {
  start: () => Promise<void>;
  resume: (after: number) => Promise<void>;
  snapshot: () => StreamCursorSnapshot;
  shouldRetry: (error: unknown) => boolean;
  onState?: (state: StreamTransportState) => void;
  maxAttempts?: number;
  sleep?: (milliseconds: number) => Promise<void>;
  random?: () => number;
};

function retryAfterMilliseconds(error: unknown): number {
  if (!error || typeof error !== "object") return 0;
  const value = (error as { retryAfterMs?: unknown }).retryAfterMs;
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : 0;
}

export async function runResumableTurnStream(options: ReconnectOptions): Promise<void> {
  const maxAttempts = options.maxAttempts ?? 4;
  const sleep = options.sleep ?? ((milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds)));
  const random = options.random ?? Math.random;
  let lastError: unknown = null;

  options.onState?.("connected");
  try {
    await options.start();
  } catch (error) {
    lastError = error;
    if (!options.snapshot().turnId || !options.shouldRetry(error)) {
      options.onState?.("offline");
      throw error;
    }
  }
  if (options.snapshot().terminal) return;
  if (!options.snapshot().turnId) {
    options.onState?.("offline");
    throw lastError ?? new Error("Stream closed before turn identity was received.");
  }

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    options.onState?.("reconnecting");
    const boundedBackoff = Math.min(4_000, 250 * 2 ** (attempt - 1));
    const jitter = Math.floor(random() * Math.min(250, boundedBackoff));
    await sleep(Math.max(boundedBackoff + jitter, retryAfterMilliseconds(lastError)));
    try {
      await options.resume(options.snapshot().appliedSequence);
      lastError = null;
      if (options.snapshot().terminal) {
        options.onState?.("connected");
        return;
      }
    } catch (error) {
      lastError = error;
      if (!options.shouldRetry(error)) {
        options.onState?.("offline");
        throw error;
      }
    }
  }

  options.onState?.("offline");
  throw lastError ?? new Error("Stream reconnect attempts were exhausted.");
}
