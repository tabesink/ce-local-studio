import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import { SseParser, InvalidSseEventError } from "../src/lib/api/sse-parser.ts";
import { createCanonicalTurnConsumer, StreamProtocolError } from "../src/features/chat-shell/stream-protocol.ts";

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
});
