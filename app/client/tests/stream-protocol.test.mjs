import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import { ApiError } from "../src/lib/api/errors.ts";
import {
  InvalidSseEventError,
  SseParser,
  StreamProtocolError,
  createCanonicalTurnConsumer,
  createEmptyTurnProjection,
  createUnavailableTurnProjection,
  extractTerminalSnapshot,
  isCursorExpiredError,
  isTerminalSnapshotDto,
  reduceTurnStreamEvent,
  replaceTurnProjectionFromTerminalSnapshot,
} from "../src/lib/stream/index.ts";

const fixtureRoot = new URL("../../tests/fixtures/sse/", import.meta.url);
const fixture = (name) => readFileSync(new URL(name, fixtureRoot), "utf8");
function chunks(text, size) {
  const result = [];
  for (let index = 0; index < text.length; index += size) result.push(text.slice(index, index + size));
  return result;
}
function consume(name, size = Number.MAX_SAFE_INTEGER) {
  const parser = new SseParser();
  const applied = [];
  const consumer = createCanonicalTurnConsumer(0, (event) => applied.push(event));
  for (const chunk of chunks(fixture(name), size)) for (const frame of parser.push(chunk)) consumer.receive(frame);
  parser.finish();
  return { applied, cursor: consumer.finish() };
}

function reduceFixture(name, size = Number.MAX_SAFE_INTEGER) {
  const { applied, cursor } = consume(name, size);
  let projection = createEmptyTurnProjection();
  for (const event of applied) projection = reduceTurnStreamEvent(projection, event);
  return { applied, cursor, projection };
}

describe("canonical turn stream protocol", () => {
  for (const size of [1, 7, Number.MAX_SAFE_INTEGER]) {
    it(`parses direct success with chunk size ${size}`, () => {
      const result = consume("direct-success.sse", size);
      assert.deepEqual(result.applied.map((event) => event.type), [
        "turn.accepted", "route.selected", "answer.delta", "turn.completed",
      ]);
      assert.deepEqual(result.cursor, { receivedSequence: 4, appliedSequence: 4 });
    });
  }
  it("ignores an exact duplicate without applying twice", () => {
    const result = consume("duplicate-delivery.sse", 3);
    assert.deepEqual(result.applied.map((event) => event.sequence), [1, 2, 3]);
  });
  it("rejects a sequence gap before applying the later event", () => {
    const parser = new SseParser();
    const applied = [];
    const consumer = createCanonicalTurnConsumer(0, (event) => applied.push(event));
    const frames = parser.push(fixture("sequence-gap.sse"));
    consumer.receive(frames[0]);
    assert.throws(() => consumer.receive(frames[1]), StreamProtocolError);
    assert.deepEqual(applied.map((event) => event.sequence), [1]);
  });
  it("recognizes cancellation as terminal", () => {
    const result = consume("cancel.sse", 5);
    assert.equal(result.applied.at(-1).type, "turn.cancelled");
    assert.equal(result.cursor.appliedSequence, 4);
  });
  it("replays a contiguous sanitized redaction ledger", () => {
    const result = consume("redacted.sse", 1);
    assert.deepEqual(result.applied.map((event) => event.sequence), [1, 2, 3, 4, 5]);
    assert.deepEqual(result.applied[2].payload, { text: "" });
    assert.deepEqual(result.applied[3].payload.citations, []);
    assert.equal(result.applied.at(-1).type, "turn.redacted");
  });
  it("rejects unsupported major versions", () => {
    const parser = new SseParser();
    const [frame] = parser.push(fixture("direct-success.sse"));
    frame.data.schemaVersion = "2.0";
    assert.throws(() => createCanonicalTurnConsumer(0, () => undefined).receive(frame), StreamProtocolError);
  });
  it("rejects a stream that closes mid-frame", () => {
    const parser = new SseParser();
    parser.push('id: evt_partial\nevent: answer.delta\ndata: {"schemaVersion":"1.0"');
    assert.throws(() => parser.finish(), InvalidSseEventError);
  });
  it("does not infer terminal state from socket close", () => {
    const parser = new SseParser();
    const consumer = createCanonicalTurnConsumer(0, () => undefined);
    consumer.receive(parser.push(fixture("direct-success.sse"))[0]);
    assert.throws(() => consumer.finish(), StreamProtocolError);
  });
  it("joins multiline data lines before JSON.parse", () => {
    const parser = new SseParser();
    const frames = parser.push(
      [
        "id: evt_ml_1",
        "event: answer.delta",
        'data: {"schemaVersion":"1.0","eventId":"evt_ml_1","turnId":"turn_ml",',
        'data: "sequence":1,"type":"answer.delta","occurredAt":"2026-07-27T12:00:00Z",',
        'data: "payload":{"text":"split"}}',
        "",
        "",
      ].join("\n"),
    );
    assert.equal(frames.length, 1);
    assert.equal(frames[0].data.payload.text, "split");
  });

  for (const size of [1, 7, Number.MAX_SAFE_INTEGER]) {
    it(`consumes evidence-only with chunk size ${size}`, () => {
      const result = reduceFixture("evidence-only.sse", size);
      assert.equal(result.applied.at(-1).type, "turn.completed");
      assert.equal(result.applied.at(-1).payload.stopReason, "evidence_only");
      assert.equal(result.projection.terminalStatus, "completed");
      assert.equal(result.projection.evidence.length, 1);
      assert.equal(result.projection.evidence[0].id, "evidence_eo_1");
    });
    it(`consumes no-grounded-context with chunk size ${size}`, () => {
      const result = reduceFixture("no-grounded-context.sse", size);
      assert.equal(result.applied.at(-1).type, "turn.completed");
      assert.equal(result.applied.at(-1).payload.stopReason, "no_grounded_context");
      assert.equal(result.projection.terminalStatus, "completed");
      assert.equal(result.projection.evidence.length, 0);
      assert.equal(result.projection.stage, null);
    });
    it(`consumes disconnect-resume with chunk size ${size}`, () => {
      const result = reduceFixture("disconnect-resume.sse", size);
      assert.equal(result.applied.at(-1).type, "turn.completed");
      assert.equal(result.projection.answerText, "Before disconnect. After resume.");
      assert.equal(result.projection.terminalStatus, "completed");
    });
    it(`consumes terminal-replay with chunk size ${size}`, () => {
      const result = reduceFixture("terminal-replay.sse", size);
      assert.equal(result.applied.at(-1).type, "turn.completed");
      assert.equal(result.applied.at(-1).payload.replay, true);
      assert.equal(result.projection.answerText, "Durable answer.");
      assert.equal(result.projection.terminalStatus, "completed");
    });
  }
});

describe("cursor expired helpers and replace semantics", () => {
  it("detects 410 cursor_expired ApiErrors and extracts terminalSnapshot", () => {
    const body = {
      error: {
        code: "cursor_expired",
        message: "The event cursor is no longer available.",
        requestId: "req_01",
      },
      terminalSnapshot: {
        turnId: "turn_01",
        status: "redacted",
        answer: null,
        evidence: [],
        citations: [],
      },
    };
    const error = new ApiError({
      status: 410,
      code: "cursor_expired",
      message: body.error.message,
      requestId: "req_01",
      fields: {},
    });
    error.terminalSnapshot = extractTerminalSnapshot(body);
    assert.equal(isCursorExpiredError(error), true);
    assert.equal(isTerminalSnapshotDto(error.terminalSnapshot), true);
    assert.deepEqual(extractTerminalSnapshot(body), body.terminalSnapshot);
    assert.equal(extractTerminalSnapshot({ error: body.error }), undefined);
  });

  it("replaces rather than merges turn projection from terminalSnapshot", () => {
    let projection = createEmptyTurnProjection();
    projection = reduceTurnStreamEvent(projection, {
      schemaVersion: "1.0",
      eventId: "evt_prior",
      turnId: "turn_stale",
      sequence: 1,
      type: "turn.accepted",
      occurredAt: "2026-07-27T12:00:00Z",
      payload: { conversationId: "conversation_1", clientRequestId: "request_1", replay: false },
    });
    projection = reduceTurnStreamEvent(projection, {
      schemaVersion: "1.0",
      eventId: "evt_answer",
      turnId: "turn_stale",
      sequence: 2,
      type: "answer.delta",
      occurredAt: "2026-07-27T12:00:01Z",
      payload: { text: "Stale partial answer that must not survive replace." },
    });
    assert.equal(projection.answerText.includes("Stale"), true);

    const snapshot = {
      turnId: "turn_01",
      status: "redacted",
      answer: null,
      evidence: [],
      citations: [],
    };
    const replaced = replaceTurnProjectionFromTerminalSnapshot(snapshot);
    assert.equal(replaced.turnId, "turn_01");
    assert.equal(replaced.answerText, "");
    assert.deepEqual(replaced.evidence, []);
    assert.equal(replaced.terminalStatus, "redacted");
    assert.equal(replaced.unavailable, false);
    assert.notEqual(replaced.answerText, projection.answerText);

    const unavailable = createUnavailableTurnProjection();
    assert.equal(unavailable.unavailable, true);
    assert.equal(unavailable.answerText, "");
    assert.match(unavailable.terminalMessage, /no longer available/i);
  });
});
