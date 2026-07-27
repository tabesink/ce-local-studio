import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const root = new URL("../..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const src = join(root, "src");
const testsRoot = join(root, "tests");

function readSrc(relativePath: string): string {
  return readFileSync(join(src, relativePath), "utf8");
}

function walk(dir: string): string[] {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (entry === "node_modules" || entry === ".next") return [];
    if (statSync(path).isDirectory()) return walk(path);
    return [path];
  });
}

function hasLocalSymbolBody(source: string, symbol: string): boolean {
  return new RegExp(
    String.raw`(export\s+)?(async\s+)?(function|const|class|let|var)\s+${symbol}\b`,
  ).test(source);
}

function isUiReexportOnly(source: string, symbol: string): boolean {
  if (hasLocalSymbolBody(source, symbol)) return false;
  return (
    new RegExp(
      String.raw`export\s+(?:\*\s+|\{\s*[^}]*\b${symbol}\b[^}]*\}\s+)from\s+["']@\/ui(?:\/[^"']*)?["']`,
    ).test(source) || /export\s+\*\s+from\s+["']@\/ui["']/.test(source)
  );
}

function isFeatureReexportOnly(source: string, symbol: string, fromPrefix: string): boolean {
  if (hasLocalSymbolBody(source, symbol)) return false;
  const escaped = fromPrefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(
    String.raw`export\s+\{\s*[^}]*\b${symbol}\b[^}]*\}\s+from\s+["']${escaped}`,
  ).test(source);
}

const STARTER_PRIMITIVES = ["Button", "Input", "StatusPill"] as const;

const ACCORDION_PARITY_RE =
  /(?:^|\/)(?:domains?-)?accordion(?:[-_/]|$)|(?:^|\/)domains-accordion(?:[-_/.]|$)/i;

describe("ui ownership structural gate", () => {
  it("requires canonical physical homes for migrated starters and compositions", () => {
    for (const name of STARTER_PRIMITIVES) {
      assert.equal(
        existsSync(join(src, `ui/${name}.tsx`)),
        true,
        `missing canonical home src/ui/${name}.tsx`,
      );
      assert.equal(
        hasLocalSymbolBody(readSrc(`ui/${name}.tsx`), name),
        true,
        `src/ui/${name}.tsx must define ${name}`,
      );
    }
    assert.equal(existsSync(join(src, "ui/index.ts")), true, "missing src/ui/index.ts");
    assert.equal(
      existsSync(join(src, "features/shell/AppShell.tsx")),
      true,
      "missing features/shell/AppShell.tsx",
    );
    assert.equal(
      hasLocalSymbolBody(readSrc("features/shell/AppShell.tsx"), "AppShell"),
      true,
      "features/shell/AppShell.tsx must define AppShell",
    );
    assert.equal(
      existsSync(join(src, "features/settings-panel/SettingsRow.tsx")),
      true,
      "missing features/settings-panel/SettingsRow.tsx",
    );
    assert.equal(
      hasLocalSymbolBody(readSrc("features/settings-panel/SettingsRow.tsx"), "SettingsRow"),
      true,
      "features/settings-panel/SettingsRow.tsx must define SettingsRow",
    );
  });

  it("rejects second physical bodies for Button/Input/StatusPill under components/ui", () => {
    for (const name of STARTER_PRIMITIVES) {
      const rel = `components/ui/${name}.tsx`;
      const path = join(src, rel);
      if (!existsSync(path)) continue;
      const body = readFileSync(path, "utf8");
      assert.equal(
        isUiReexportOnly(body, name),
        true,
        `${rel} must not host a competing implementation (alias-only from @/ui or delete)`,
      );
    }
  });

  it("rejects second physical bodies for starters and SettingsRow in _shared/ui", () => {
    const shared = readSrc("_shared/ui/index.tsx");
    for (const name of STARTER_PRIMITIVES) {
      assert.equal(
        hasLocalSymbolBody(shared, name),
        false,
        `_shared/ui must not define ${name}; re-export from @/ui only`,
      );
    }
    assert.equal(
      hasLocalSymbolBody(shared, "SettingsRow"),
      false,
      "_shared/ui must not define SettingsRow; home is features/settings-panel",
    );
  });

  it("allows only an alias for AppShell under components/layout", () => {
    const aliasPath = join(src, "components/layout/AppShell.tsx");
    if (!existsSync(aliasPath)) return;
    const body = readFileSync(aliasPath, "utf8");
    assert.equal(
      isFeatureReexportOnly(body, "AppShell", "@/features/shell"),
      true,
      "components/layout/AppShell.tsx must alias @/features/shell (no second body)",
    );
  });

  it("requires Settings Domain accordion parity under settings-panel ownership", () => {
    assert.equal(
      existsSync(join(src, "features/settings-panel/DomainAccordionRow.tsx")),
      true,
      "missing features/settings-panel/DomainAccordionRow.tsx",
    );
    assert.equal(
      hasLocalSymbolBody(readSrc("features/settings-panel/DomainAccordionRow.tsx"), "DomainAccordionRow"),
      true,
      "DomainAccordionRow.tsx must define DomainAccordionRow",
    );
    assert.equal(
      existsSync(join(src, "ui/Accordion.tsx")),
      false,
      "shared Accordion under src/ui is forbidden; accordion remains Settings-owned",
    );
    const parityRoot = join(testsRoot, "parity");
    for (const rel of [
      "manifests/domains-accordion.json",
      "fixtures/domains-accordion.html",
      "react/domains-accordion.test.tsx",
    ]) {
      assert.equal(
        existsSync(join(parityRoot, rel)),
        true,
        `missing Domain accordion parity artifact: ${rel}`,
      );
    }
    const offenders = walk(parityRoot)
      .map((file) => relative(parityRoot, file).split("\\").join("/"))
      .filter((rel) => ACCORDION_PARITY_RE.test(rel) && !rel.includes("domains-accordion"));
    assert.deepEqual(
      offenders,
      [],
      `Only domains-accordion parity target is allowed. Offenders: ${offenders.join(", ")}`,
    );
  });
});

