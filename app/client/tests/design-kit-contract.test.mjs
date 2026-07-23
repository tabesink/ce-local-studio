import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const src = join(root, "src");
const repoRoot = join(root, "..", "..");

function read(relativePath) {
  return readFileSync(join(root, relativePath), "utf8");
}

function readRepo(relativePath) {
  return readFileSync(join(repoRoot, relativePath), "utf8");
}

function walk(dir) {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (entry === "node_modules" || entry === ".next") return [];
    if (statSync(path).isDirectory()) return walk(path);
    return [path];
  });
}

function sourceFiles() {
  return walk(src).filter((file) => /\.(ts|tsx)$/.test(file));
}

function toPosix(filePath) {
  return relative(src, filePath).split("\\").join("/");
}

/** Legacy @_shared/ui call sites allowed until a migration slice. Barrel + CE-only helpers may keep importing the internal kit. */
const SHARED_UI_IMPORT_ALLOWLIST = new Set([
  "components/ui/index.ts",
  "components/ui/AppLogo.tsx",
  "features/chat-shell/ChatShell.tsx",
  "features/chat-shell/EvidencePanel.tsx",
  "features/documents/DocumentsPage.tsx",
  "features/documents/PdfPreview.tsx",
  "features/graph/GraphPage.tsx",
  "features/navigation-sidebar/NavigationSidebar.tsx",
  "features/user-preferences/PreferencesPanel.tsx",
]);

const SHARED_UI_IMPORT_RE = /from\s+["']@\/_shared\/ui["']/;

describe("design kit contract", () => {
  it("exposes an app UI barrel that re-exports the shared kit plus CE-only surfaces", () => {
    const barrelPath = join(src, "components/ui/index.ts");
    assert.equal(existsSync(barrelPath), true, "frontend/src/components/ui/index.ts must exist");
    const barrel = read("src/components/ui/index.ts");
    assert.match(barrel, /export\s+\*\s+from\s+["']@\/_shared\/ui["']/);
    assert.match(barrel, /export\s+\{\s*AppLogo\s*\}/);
    assert.match(barrel, /export\s+\{\s*ErrorBox\s*\}/);
    assert.match(barrel, /export\s+\{\s*PageState\s*\}/);
    assert.match(barrel, /@\/components\/ui/);
    assert.match(read("src/_shared/ui/index.tsx"), /export function ToggleSwitch/);
  });

  it("DESIGN.md states the canonical ownership and brownfield migration boundary", () => {
    const design = readRepo("DESIGN.md");
    assert.match(design, /src\/ui/);
    assert.match(design, /components\/ui/);
    assert.match(design, /_shared\/ui/);
    assert.match(design, /brownfield inventory/);
    assert.match(design, /cannot justify a second physical kit/);
    assert.match(design, /Documentation acceptance does not prove application parity/);
  });

  it("frontend agent guidance points at canonical ownership and forbids new legacy call sites", () => {
    const guidelines = readRepo("docs/frontend/AGENTS.md");
    assert.match(guidelines, /src\/ui/);
    assert.match(guidelines, /Temporary legacy import specifiers/);
    assert.match(guidelines, /cannot contain competing implementations/);
    assert.match(guidelines, /cannot.*receive new call sites/i);
    assert.match(guidelines, /zai-dark/);
    assert.match(guidelines, /zai-light/);
  });

  it("forbids new @_shared/ui imports outside the allowlist (going-forward)", () => {
    const offenders = [];
    for (const file of sourceFiles()) {
      const rel = toPosix(file);
      const body = readFileSync(file, "utf8");
      if (!SHARED_UI_IMPORT_RE.test(body)) continue;
      if (SHARED_UI_IMPORT_ALLOWLIST.has(rel)) continue;
      offenders.push(rel);
    }
    assert.deepEqual(
      offenders,
      [],
      `New @_shared/ui imports must use @/components/ui instead. Offenders: ${offenders.join(", ")}`,
    );
  });

  it("allowlist covers every current @_shared/ui importer (characterization)", () => {
    const importers = [];
    for (const file of sourceFiles()) {
      const rel = toPosix(file);
      const body = readFileSync(file, "utf8");
      if (SHARED_UI_IMPORT_RE.test(body)) importers.push(rel);
    }
    importers.sort();
    const allowlisted = [...SHARED_UI_IMPORT_ALLOWLIST].sort();
    for (const rel of importers) {
      assert.equal(
        SHARED_UI_IMPORT_ALLOWLIST.has(rel),
        true,
        `Importer ${rel} missing from SHARED_UI_IMPORT_ALLOWLIST — update allowlist when characterizing, not when adding new feature imports`,
      );
    }
    for (const rel of allowlisted) {
      assert.equal(
        importers.includes(rel),
        true,
        `Allowlist entry ${rel} no longer imports @_shared/ui — remove it from the allowlist`,
      );
    }
  });
});
