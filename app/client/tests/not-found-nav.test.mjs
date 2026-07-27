import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const src = join(root, "src");

function walk(dir) {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (entry === "node_modules" || entry === ".next") return [];
    if (statSync(path).isDirectory()) return walk(path);
    return [path];
  });
}

describe("DRIFT-04 not-found and deferred-route residuals (P9-04 U5)", () => {
  it("renders shell-safe not-found without product-data fetches", () => {
    const pagePath = join(src, "app/not-found.tsx");
    assert.equal(existsSync(pagePath), true, "missing src/app/not-found.tsx");
    const page = readFileSync(pagePath, "utf8");
    assert.match(page, /AppShell/);
    assert.match(page, /PageState/);
    assert.match(page, /Not found/);
    assert.match(page, /This surface is not available/);
    assert.doesNotMatch(page, /useEffect/);
    assert.doesNotMatch(page, /ceFetch/);
    assert.doesNotMatch(page, /listAdminDomains|listMemberDomains/);
    assert.doesNotMatch(page, /stack|trace|runtimeUrl|password|credential/i);
  });

  it("keeps deferred Phase 2/3 routes out of the app route tree and Phase 1 nav", () => {
    const appPages = walk(join(src, "app"))
      .filter((file) => file.endsWith("page.tsx"))
      .map((file) => relative(join(src, "app"), file).split("\\").join("/"));
    for (const deferred of ["logs/page.tsx", "usage/page.tsx", "wiki/page.tsx", "server/page.tsx"]) {
      assert.equal(appPages.includes(deferred), false, `deferred route must stay absent: ${deferred}`);
    }

    const registry = readFileSync(join(src, "features/navigation-sidebar/constants.ts"), "utf8");
    for (const hidden of ['"/logs"', '"/usage"', '"/wiki"', '"/server"', '"/dashboard"', '"/recipes"', '"/plugins"']) {
      assert.equal(registry.includes(hidden), false, hidden);
    }
    assert.match(registry, /Phase 1 nav registry/);
  });

  it("keeps graph unavailable no-request proof intact", () => {
    const page = readFileSync(join(src, "features/graph/GraphPage.tsx"), "utf8");
    assert.match(page, /Graph visualization is not available/);
    assert.doesNotMatch(page, /listMemberDomains/);
    assert.doesNotMatch(page, /ceFetch/);
    assert.doesNotMatch(page, /useEffect/);
  });
});
