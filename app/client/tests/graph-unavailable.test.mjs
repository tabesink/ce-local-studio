import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

describe("Graph unavailable no-request (P9-03 U6 / DRIFT-04)", () => {
  it("renders static unavailable copy with zero product-data fetches", () => {
    const page = readFileSync(join(root, "src/features/graph/GraphPage.tsx"), "utf8");

    assert.match(page, /Graph visualization is not available/);
    assert.match(page, /graph-unavailable/);
    assert.doesNotMatch(page, /listMemberDomains/);
    assert.doesNotMatch(page, /useEffect/);
    assert.doesNotMatch(page, /ceFetch/);
    assert.doesNotMatch(page, /["'`]\/domains/);
    assert.doesNotMatch(page, /from\s+["']@\/features\/domains/);
    assert.doesNotMatch(page, /<select/);
  });
});
