import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

describe("Graph workbench structure (P12-07 U10)", () => {
  it("uses generated graph client paths and workbench shell", () => {
    const page = readFileSync(join(root, "src/features/graph/GraphPage.tsx"), "utf8");
    const api = readFileSync(join(root, "src/features/graph/api.ts"), "utf8");

    assert.match(page, /graph-workbench/);
    assert.match(page, /listMemberDomains/);
    assert.match(page, /Knowledge Domain/);
    assert.doesNotMatch(page, /graph-unavailable/);
    assert.doesNotMatch(page, /Graph visualization is not available/);
    assert.match(api, /\/domains\/\$\{encodeURIComponent\(domainId\)\}\/graph/);
    assert.match(api, /graph\/labels/);
    assert.doesNotMatch(api, /\/graphs/);
    assert.doesNotMatch(api, /lightrag/i);
  });
});
