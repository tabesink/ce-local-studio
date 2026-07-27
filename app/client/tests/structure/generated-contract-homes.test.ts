import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const root = new URL("../..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const src = join(root, "src");
const generatedDir = join(src, "lib/api/generated");

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

/** Handwritten public product DTO object types outside generated aliases (thin `{ user: CurrentUser }` envelopes allowed). */
const HANDWRITTEN_PUBLIC_DTO_RE =
  /export\s+type\s+(CurrentUser|SessionInfo|AdminUser\w*|DocumentSummary\w*|Evidence\w*Dto)\s*=\s*\{/;

describe("generated contract / barrel hygiene gate", () => {
  it("keeps generated OpenAPI/SSE homes under lib/api/generated", () => {
    assert.equal(existsSync(join(generatedDir, "openapi.ts")), true);
    assert.equal(existsSync(join(generatedDir, "sse.ts")), true);
    const misplaced = walk(src)
      .filter((file) => /generated[/\\](openapi|sse)\.ts$/.test(file))
      .map(toPosix)
      .filter((rel) => !rel.startsWith("lib/api/generated/"));
    assert.deepEqual(misplaced, [], `Misplaced generated files: ${misplaced.join(", ")}`);
  });

  it("rejects handwritten public auth/user DTO object substitutes", () => {
    const offenders: string[] = [];
    for (const file of walk(src).filter((f) => /\.(ts|tsx)$/.test(f))) {
      const rel = toPosix(file);
      if (rel.startsWith("lib/api/generated/")) continue;
      const source = readFileSync(file, "utf8");
      if (HANDWRITTEN_PUBLIC_DTO_RE.test(source)) {
        offenders.push(rel);
      }
    }
    assert.deepEqual(
      offenders,
      [],
      `Handwritten public DTO substitutes (use components["schemas"] aliases): ${offenders.join(", ")}`,
    );
  });

  it("keeps types/auth.ts as generated aliases only", () => {
    const authTypes = readFileSync(join(src, "types/auth.ts"), "utf8");
    assert.match(authTypes, /components\["schemas"\]\["CurrentUserDto"\]/);
    assert.match(authTypes, /components\["schemas"\]\["LoginRequest"\]/);
    assert.doesNotMatch(authTypes, /username\s*:/);
    assert.doesNotMatch(authTypes, /isDisabled/);
  });
});
