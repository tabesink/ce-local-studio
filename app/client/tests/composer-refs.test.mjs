import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

function read(rel) {
  return readFileSync(join(root, rel), "utf8");
}

describe("Composer refs UI (P9-07 U2 / M-09)", () => {
  it("discovers only source and template kinds and filters evidence", () => {
    const hook = read("src/features/chat-shell/use-chat-shell.ts");
    assert.match(hook, /kinds:\s*\[\s*"source"\s*,\s*"template"\s*\]/);
    assert.match(hook, /ref\.kind === "source" \|\| ref\.kind === "template"/);
    assert.match(hook, /if \(ref\.kind === "evidence"\) return/);
  });

  it("keeps tokens in memory-only chip state and never writes storage APIs", () => {
    const hook = read("src/features/chat-shell/use-chat-shell.ts");
    const shell = read("src/features/chat-shell/ChatShell.tsx");
    assert.match(hook, /composerRefs/);
    assert.match(shell, /data-testid="composer-ref-chips"/);
    assert.equal(hook.includes("localStorage"), false);
    assert.equal(hook.includes("sessionStorage"), false);
    assert.equal(shell.includes("localStorage"), false);
  });
});
