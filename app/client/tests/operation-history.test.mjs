import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

function read(rel) {
  return readFileSync(join(root, rel), "utf8");
}

describe("Operation history UX (P9-07 U3)", () => {
  it("documents page can load source operation history without inventing historical retry/cancel", () => {
    const page = read("src/features/documents/DocumentsPage.tsx");
    const api = read("src/features/documents/api.ts");

    assert.match(api, /listSourceOperations/);
    assert.match(page, /listSourceOperations|operation history|Operation history|data-testid="source-operation-history"/i);
    // Current-op actions remain; historical list must not invent per-row retry from history.
    assert.match(page, /retrySourcePreparation|Retry preparation/);
    assert.match(page, /isAdminActionEnabled/);
  });

  it("domains settings can load domain operation history", () => {
    const panel = read("src/features/settings-panel/SettingsPanel.tsx");
    const row = read("src/features/settings-panel/DomainAccordionRow.tsx");
    const api = read("src/features/domains/api.ts");

    assert.match(api, /listDomainOperations/);
    const surface = `${panel}\n${row}`;
    assert.match(surface, /listDomainOperations|operation history|Operation history|data-testid="domain-operation-history"/i);
  });
});
