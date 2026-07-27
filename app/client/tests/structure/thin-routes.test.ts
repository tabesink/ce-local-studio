import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const root = new URL("../..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const src = join(root, "src");
const appDir = join(src, "app");

/** Non-page app chrome may hold bootstrap; product pages may not. */
const NON_PAGE_ALLOWLIST = new Set(["providers.tsx", "layout.tsx"]);

function walk(dir: string): string[] {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (entry === "node_modules" || entry === ".next" || entry === "api") return [];
    if (statSync(path).isDirectory()) return walk(path);
    return [path];
  });
}

function toPosix(filePath: string): string {
  return relative(appDir, filePath).split("\\").join("/");
}

const ALLOWED_IMPORT_PREFIXES = [
  "@/features/",
  "@/ui",
  "@/components/ui/",
  "@/components/layout/",
  "next/",
  "react",
  "react/",
  "react-dom",
];

function importAllowed(specifier: string): boolean {
  if (specifier === "@/ui" || specifier.startsWith("@/ui/")) return true;
  return ALLOWED_IMPORT_PREFIXES.some(
    (prefix) => specifier === prefix.replace(/\/$/, "") || specifier.startsWith(prefix),
  );
}

describe("thin route structural gate", () => {
  it("keeps page.tsx / not-found.tsx as thin shells", () => {
    const routeFiles = walk(appDir).filter((file) => {
      const base = file.split(/[/\\]/).pop() ?? "";
      return base === "page.tsx" || base === "not-found.tsx";
    });
    assert.ok(routeFiles.length >= 7, "expected Phase 1 route pages");

    const offenders: string[] = [];
    for (const file of routeFiles) {
      const rel = toPosix(file);
      const source = readFileSync(file, "utf8");
      if (/\buseState\b|\buseAuthStore\b|\buseEffect\b/.test(source)) {
        offenders.push(`${rel}: orchestration hooks in route shell`);
      }
      if (/\bceFetch\b|\bfetch\s*\(/.test(source)) {
        offenders.push(`${rel}: network call in route shell`);
      }
      for (const match of source.matchAll(/from\s+["']([^"']+)["']/g)) {
        const specifier = match[1];
        if (specifier.startsWith(".")) {
          offenders.push(`${rel}: relative import ${specifier} (use feature/ui aliases)`);
        } else if (specifier.startsWith("@/") && !importAllowed(specifier)) {
          offenders.push(`${rel}: disallowed import ${specifier}`);
        }
      }
    }
    assert.deepEqual(offenders, [], `Thick or illegal route shells:\n${offenders.join("\n")}`);
  });

  it("documents non-page app chrome allowlist", () => {
    for (const name of NON_PAGE_ALLOWLIST) {
      assert.equal(existsSync(join(appDir, name)), true, `missing allowlisted app chrome ${name}`);
    }
  });
});
