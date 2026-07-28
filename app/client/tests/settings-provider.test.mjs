import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

function read(rel) {
  return readFileSync(join(root, rel), "utf8");
}

describe("Provider Settings live section (P9-07 U6)", () => {
  it("uses generated DTO fields and If-Match mutations", () => {
    const api = read("src/features/settings-panel/api.ts");
    const panel = read("src/features/settings-panel/SettingsPanel.tsx");

    assert.match(api, /ProviderSummaryDto/);
    assert.match(api, /rotateProviderCredential\([\s\S]*version:\s*number/);
    assert.match(api, /patchRuntimeSettings\([\s\S]*version:\s*number/);
    assert.doesNotMatch(api, /isConfigured:\s*boolean/);
    assert.match(panel, /provider\.kind/);
    assert.match(panel, /provider\.configured/);
    assert.match(panel, /requiresCredentials/);
    assert.match(panel, /Replace credential|Add credential/);
    assert.match(panel, /Active synthesis model/);
    assert.match(panel, /Embedding profiles/);
    assert.match(panel, /In-flight work keeps its frozen configuration/);
    assert.doesNotMatch(panel, /createModelProfile\(/);
    assert.doesNotMatch(panel, /provider\.isConfigured|providerKind=/);
    const providerFn = panel.slice(panel.indexOf("function ProviderSection"), panel.indexOf("function DomainsSection"));
    assert.doesNotMatch(providerFn, /runtime-ready|runtimeReady/);
    assert.match(providerFn, /requiresCredentials/);
  });
});
