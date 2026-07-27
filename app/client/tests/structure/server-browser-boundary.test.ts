import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const root = new URL("../..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const src = join(root, "src");

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

function isServerEnvFile(rel: string): boolean {
  return (
    rel === "middleware.ts" ||
    rel.startsWith("lib/server/") ||
    /^app\/api\/.+\/route\.tsx?$/.test(rel)
  );
}

describe("server/browser boundary structural gate", () => {
  it("keeps CONTEXT_ENGINE_* only in server files", () => {
    const offenders: string[] = [];
    for (const file of walk(src).filter((f) => /\.(ts|tsx)$/.test(f))) {
      const rel = toPosix(file);
      const source = readFileSync(file, "utf8");
      if (!/CONTEXT_ENGINE_/.test(source)) continue;
      if (!isServerEnvFile(rel)) {
        offenders.push(rel);
      }
    }
    assert.deepEqual(offenders, [], `CONTEXT_ENGINE_* leaked into browser modules: ${offenders.join(", ")}`);
  });

  it("forbids browser modules from importing lib/server", () => {
    const offenders: string[] = [];
    for (const file of walk(src).filter((f) => /\.(ts|tsx)$/.test(f))) {
      const rel = toPosix(file);
      if (rel.startsWith("lib/server/") || /^app\/api\//.test(rel)) continue;
      const source = readFileSync(file, "utf8");
      if (/from\s+["']@\/lib\/server(?:\/[^"']*)?["']/.test(source) || /from\s+["']\.\.\/.*lib\/server/.test(source)) {
        offenders.push(rel);
      }
    }
    assert.deepEqual(offenders, [], `Browser modules import lib/server: ${offenders.join(", ")}`);
  });
});
