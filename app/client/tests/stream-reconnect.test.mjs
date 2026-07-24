import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { runResumableTurnStream } from "../src/features/chat-shell/stream-reconnect.ts";

function state() {
  return { receivedSequence: 0, appliedSequence: 0, turnId: null, terminal: false };
}

describe("bounded turn stream reconnect", () => {
  it("resumes from the last applied cursor and honors Retry-After", async () => {
    const cursor = state();
    const after = [];
    const delays = [];
    const states = [];
    let resumes = 0;
    await runResumableTurnStream({
      start: async () => { cursor.turnId = "turn_1"; cursor.receivedSequence = 1; cursor.appliedSequence = 1; },
      resume: async (value) => {
        after.push(value);
        resumes += 1;
        if (resumes === 1) throw Object.assign(new Error("busy"), { retryAfterMs: 900 });
        cursor.receivedSequence = 2;
        cursor.appliedSequence = 2;
        cursor.terminal = true;
      },
      snapshot: () => ({ ...cursor }),
      shouldRetry: () => true,
      onState: (value) => states.push(value),
      sleep: async (value) => { delays.push(value); },
      random: () => 0,
    });
    assert.deepEqual(after, [1, 1]);
    assert.deepEqual(delays, [250, 900]);
    assert.deepEqual(states, ["connected", "reconnecting", "reconnecting", "connected"]);
  });

  it("stops immediately for a non-retryable protocol conflict", async () => {
    const cursor = { ...state(), turnId: "turn_1", appliedSequence: 1, receivedSequence: 2 };
    const conflict = new Error("conflicting sequence");
    const states = [];
    await assert.rejects(
      runResumableTurnStream({
        start: async () => { throw conflict; },
        resume: async () => { throw new Error("must not resume"); },
        snapshot: () => ({ ...cursor }),
        shouldRetry: () => false,
        onState: (value) => states.push(value),
      }),
      conflict,
    );
    assert.deepEqual(states, ["connected", "offline"]);
  });

  it("enters offline after bounded non-terminal resumes", async () => {
    const cursor = { ...state(), turnId: "turn_1", appliedSequence: 1, receivedSequence: 1 };
    const states = [];
    let resumes = 0;
    await assert.rejects(
      runResumableTurnStream({
        start: async () => undefined,
        resume: async (after) => { assert.equal(after, 1); resumes += 1; },
        snapshot: () => ({ ...cursor }),
        shouldRetry: () => true,
        onState: (value) => states.push(value),
        maxAttempts: 3,
        sleep: async () => undefined,
        random: () => 0,
      }),
      /exhausted/,
    );
    assert.equal(resumes, 3);
    assert.equal(states.at(-1), "offline");
  });
});
