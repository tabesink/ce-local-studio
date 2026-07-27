import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const root = new URL("../..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const src = join(root, "src");

const SHARED_UI_IMPORT_ALLOWLIST = new Set([
  "components/ui/index.ts",
  "components/ui/AppLogo.tsx",
  "features/documents/DocumentsPage.tsx",
  "features/documents/PdfPreview.tsx",
  "features/graph/GraphPage.tsx",
  "features/navigation-sidebar/NavigationSidebar.tsx",
  "features/settings-panel/SettingsRow.tsx",
  "features/user-preferences/PreferencesPanel.tsx",
]);

function walk(dir: string): string[] {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (entry === "node_modules" || entry === ".next") return [];
    if (statSync(path).isDirectory()) return walk(path);
    return [path];
  });
}

function toPosix(filePath: string): string {
  return relative(src, filePath).split("\\").join("/");
}

function sourceFiles(): string[] {
  return walk(src).filter((file) => /\.(ts|tsx)$/.test(file));
}

type Layer = "app" | "features" | "lib" | "lib-server" | "ui" | "components" | "_shared" | "types" | "other";

function layerOf(relPosix: string): Layer {
  if (relPosix.startsWith("lib/server/") || relPosix === "lib/server") return "lib-server";
  const top = relPosix.split("/")[0] ?? "";
  if (
    top === "app" ||
    top === "features" ||
    top === "lib" ||
    top === "ui" ||
    top === "components" ||
    top === "_shared" ||
    top === "types"
  ) {
    return top;
  }
  return "other";
}

function edgeAllowed(from: Layer, to: Layer, fromRel: string, toRel: string): boolean {
  if (to === "lib-server") {
    return from === "lib-server" || fromRel.startsWith("app/api/");
  }
  if (from === "ui") return to === "ui" || to === "types";
  if (from === "lib") return to === "lib" || to === "ui" || to === "types";
  if (from === "lib-server") return to === "lib-server" || to === "lib" || to === "types";
  if (from === "features") {
    if (to === "app") return false;
    if (to === "_shared") return SHARED_UI_IMPORT_ALLOWLIST.has(fromRel);
    if (to === "components") {
      return (
        SHARED_UI_IMPORT_ALLOWLIST.has(fromRel) ||
        toRel === "components/ui" ||
        toRel.startsWith("components/ui/") ||
        toRel === "components/layout" ||
        toRel.startsWith("components/layout/")
      );
    }
    return to === "features" || to === "lib" || to === "ui" || to === "types";
  }
  if (from === "app") {
    if (to === "lib-server") return fromRel.startsWith("app/api/");
    return true;
  }
  return true;
}

const IMPORT_RE = /from\s+["']([^"']+)["']/g;

describe("import direction structural gate", () => {
  it("forbids reverse layers, browser→lib/server, and .references imports", () => {
    assert.equal(existsSync(join(src, "state")), false, "src/state must be removed; auth lives under features/auth");

    const offenders: string[] = [];
    for (const file of sourceFiles()) {
      const fromRel = toPosix(file);
      const fromLayer = layerOf(fromRel);
      const source = readFileSync(file, "utf8");
      for (const match of source.matchAll(IMPORT_RE)) {
        const specifier = match[1];
        if (specifier.includes(".references")) {
          offenders.push(`${fromRel} -> ${specifier} (.references)`);
          continue;
        }
        if (!specifier.startsWith("@/")) continue;
        const toRel = specifier.slice(2).replace(/\\/g, "/");
        const toLayer = layerOf(toRel);
        if (!edgeAllowed(fromLayer, toLayer, fromRel, toRel)) {
          offenders.push(`${fromRel} (${fromLayer}) -> ${toRel} (${toLayer})`);
        }
      }
    }
    assert.deepEqual(offenders, [], `Forbidden import edges:\n${offenders.join("\n")}`);
  });
});
