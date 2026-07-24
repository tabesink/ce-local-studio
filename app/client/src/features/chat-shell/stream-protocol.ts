export type CanonicalTurnEnvelope = {
  schemaVersion: string;
  eventId: string;
  turnId: string;
  sequence: number;
  type: string;
  occurredAt: string;
  payload: object;
};
export type SseFrame = { id: string; event: string; data: Record<string, unknown> };

const TURN_EVENT_TYPES = new Set([
  "turn.accepted", "route.selected", "retrieval.started", "retrieval.completed", "evidence.delta",
  "answer.delta", "turn.completed", "turn.failed", "turn.cancelled", "turn.redacted",
]);
const TERMINAL_EVENT_TYPES = new Set(["turn.completed", "turn.failed", "turn.cancelled", "turn.redacted"]);

export class StreamProtocolError extends Error {
  readonly code = "stream_protocol_error";
  constructor(message: string) {
    super(message);
    this.name = "StreamProtocolError";
  }
}

type ErrorFactory = (message: string) => Error;

export function createCanonicalTurnConsumer<Event extends CanonicalTurnEnvelope>(
  after: number,
  onEvent: (event: Event) => void,
  errorFactory: ErrorFactory = (message) => new StreamProtocolError(message),
) {
  let receivedSequence = after;
  let appliedSequence = after;
  let turnId: string | null = null;
  let terminal = false;
  const sequenceDigests = new Map<number, string>();
  const eventIds = new Map<string, number>();

  return {
    receive(frame: SseFrame) {
      const value = frame.data;
      const schemaVersion = value["schemaVersion"];
      const eventId = value["eventId"];
      const envelopeTurnId = value["turnId"];
      const sequence = value["sequence"];
      const type = value["type"];
      const occurredAt = value["occurredAt"];
      const payload = value["payload"];
      if (
        typeof schemaVersion !== "string" || schemaVersion.split(".")[0] !== "1" ||
        typeof eventId !== "string" || typeof envelopeTurnId !== "string" ||
        !Number.isInteger(sequence) || (sequence as number) < 1 || typeof type !== "string" ||
        typeof occurredAt !== "string" || !payload || typeof payload !== "object" || Array.isArray(payload) ||
        frame.id !== eventId || frame.event !== type
      ) throw errorFactory("The stream envelope was invalid or unsupported.");

      const numericSequence = sequence as number;
      receivedSequence = Math.max(receivedSequence, numericSequence);
      if (turnId !== null && turnId !== envelopeTurnId) throw errorFactory("The stream changed turn identity.");
      turnId = envelopeTurnId;
      const digest = JSON.stringify(value);
      if (numericSequence <= appliedSequence) {
        if (sequenceDigests.get(numericSequence) === digest && eventIds.get(eventId) === numericSequence) return;
        throw errorFactory("The stream sequence regressed or conflicted.");
      }
      if (numericSequence !== appliedSequence + 1) {
        throw errorFactory(`The stream has a sequence gap after ${appliedSequence}.`);
      }
      sequenceDigests.set(numericSequence, digest);
      eventIds.set(eventId, numericSequence);
      appliedSequence = numericSequence;
      if (!TURN_EVENT_TYPES.has(type)) return;
      const event = value as Event;
      if (TERMINAL_EVENT_TYPES.has(event.type)) terminal = true;
      onEvent(event);
    },
    snapshot() {
      return { receivedSequence, appliedSequence, turnId, terminal };
    },
    finish() {
      if (!terminal) throw errorFactory(`The stream closed before a terminal event at ${appliedSequence}.`);
      return { receivedSequence, appliedSequence };
    },
  };
}
