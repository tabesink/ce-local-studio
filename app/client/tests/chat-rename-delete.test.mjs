import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

function read(rel) {
  return readFileSync(join(root, rel), "utf8");
}

describe("Conversation rename/delete (P9-07 U2 / M-08)", () => {
  it("rename and delete adapters require If-Match from conversation version", () => {
    const api = read("src/features/chat-shell/api.ts");
    assert.match(api, /renameConversation\([\s\S]*?version:\s*number/);
    assert.match(api, /deleteConversation\([\s\S]*?version:\s*number/);
    assert.match(api, /ifMatchHeader\(version\)/);
    assert.match(api, /Conversation version is required for rename/);
    assert.match(api, /Conversation version is required for delete/);
  });

  it("chat shell exposes rename/delete controls with confirmation", () => {
    const shell = read("src/features/chat-shell/ChatShell.tsx");
    const hook = read("src/features/chat-shell/use-chat-shell.ts");

    assert.match(hook, /renameActiveConversation/);
    assert.match(hook, /deleteActiveConversation/);
    assert.match(shell, /data-testid="conversation-rename"/);
    assert.match(shell, /data-testid="conversation-delete"/);
    assert.match(shell, /Delete conversation/);
    assert.match(shell, /UiModal/);
  });
});
