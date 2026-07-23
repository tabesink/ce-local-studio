import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

function read(relativePath) {
  return readFileSync(join(root, relativePath), "utf8");
}

describe("Settings Users read-only account status", () => {
  it("uses only the contracted admin user-list endpoint", () => {
    const api = read("src/features/settings-panel/api.ts");

    assert.match(api, /export async function listUsers/);
    assert.match(api, /\"\/admin\/users\"/);
    assert.equal(api.includes("updateUserDisabled"), false);
    assert.equal(api.includes('/admin/users/${'), false);
    assert.equal(api.includes("UserDisabledPatchRequest"), false);
  });

  it("renders user roles and status without mutation controls", () => {
    const panel = read("src/features/settings-panel/SettingsPanel.tsx");

    assert.match(panel, /label: "Users"/);
    assert.match(panel, /Read-only account status/);
    assert.match(panel, /row\.role/);
    assert.match(panel, /StatusPill tone="danger">Disabled/);
    assert.match(panel, /StatusPill tone="good">Active/);
    assert.equal(panel.includes("updateUserDisabled"), false);
    assert.equal(panel.includes("Current administrator cannot be disabled"), false);
    assert.equal(panel.includes("Disable user"), false);
  });
});
