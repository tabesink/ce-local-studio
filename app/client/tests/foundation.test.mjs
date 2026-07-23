import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const src = join(root, "src");

function read(relativePath) {
  return readFileSync(join(root, relativePath), "utf8");
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
  return walk(src).filter((file) => /\.(ts|tsx|css)$/.test(file));
}

describe("F-009 foundation", () => {
  it("defines exactly the Phase 1 page-route map", () => {
    const expectedRoutes = [
      "src/app/chat/page.tsx",
      "src/app/database-visualize/page.tsx",
      "src/app/documents/page.tsx",
      "src/app/forbidden/page.tsx",
      "src/app/login/page.tsx",
      "src/app/page.tsx",
      "src/app/settings/page.tsx",
    ];
    const actualRoutes = walk(join(src, "app"))
      .filter((file) => file.endsWith("page.tsx"))
      .map((file) => relative(root, file))
      .sort();
    assert.deepEqual(actualRoutes, expectedRoutes);
  });

  it("wires the API proxy through Next.js middleware", () => {
    assert.equal(existsSync(join(src, "middleware.ts")), true, "src/middleware.ts must exist");
    assert.equal(existsSync(join(src, "proxy.ts")), false, "src/proxy.ts must not shadow middleware.ts");
    const middleware = read("src/middleware.ts");
    assert.match(middleware, /export function middleware/);
    assert.match(middleware, /"\/api\/v1\/:path\*"/);
    assert.match(middleware, /CONTEXT_ENGINE_API_BASE/);
  });

  it("logs out disabled or revoked sessions on any 401 response", () => {
    // Backend returns 401 for disabled users on every request; the client must
    // flip the auth store to unauthenticated, and the layout must redirect.
    const client = read("src/lib/api/client.ts");
    assert.match(client, /response\.status === 401[^\n]*handleUnauthorized/);
    assert.match(client, /unauthorizedHandler\?\.\(\)/);
    const providers = read("src/app/providers.tsx");
    assert.match(providers, /setUnauthorizedHandler\(\(\) => \{\s*markUnauthenticated\(\);/);
    const layout = read("src/components/layout/AppLayout.tsx");
    assert.match(layout, /status === "unauthenticated"/);
    assert.match(layout, /router\.replace\("\/login"\)/);
  });

  it("applies persisted appearance preferences before paint via central runtime", () => {
    const layout = read("src/app/layout.tsx");
    assert.match(layout, /getAppearanceBootstrapScript/);
    assert.match(layout, /dangerouslySetInnerHTML/);

    const providers = read("src/app/providers.tsx");
    assert.match(providers, /AppearanceProvider/);
    assert.equal(providers.includes("dataset.theme"), false);
    assert.equal(providers.includes("dataset.density"), false);
    assert.equal(providers.includes('readUiPreference("ce.theme")'), false);

    const runtime = read("src/features/user-preferences/appearanceRuntime.ts");
    assert.match(runtime, /export function applyAppearance/);
    assert.match(runtime, /export function readAppearance/);

    const preferences = read("src/features/user-preferences/PreferencesPanel.tsx");
    assert.match(preferences, /useAppearance/);
    assert.equal(preferences.includes("dataset.theme"), false);
    assert.equal(preferences.includes("writeUiPreference"), false);

    const css = read("src/app/globals.css");
    assert.match(css, /\[data-density="comfortable"\]/);
  });

  it("keeps data-theme and data-density writes inside the appearance runtime", () => {
    const allowed = new Set([
      join("src", "features", "user-preferences", "appearanceRuntime.ts"),
      join("src", "features", "user-preferences", "appearanceBootstrap.ts"),
    ]);
    const offenders = sourceFiles()
      .filter((file) => !allowed.has(relative(root, file)))
      .filter((file) => {
        const source = readFileSync(file, "utf8");
        return /dataset\.theme\s*=/.test(source) || /dataset\.density\s*=/.test(source);
      })
      .map((file) => relative(root, file));
    assert.deepEqual(offenders, []);
  });

  it("keeps direct fetch isolated to shared API and SSE wrappers", () => {
    const allowed = new Set([
      join("src", "lib", "api", "client.ts"),
      join("src", "lib", "api", "sse.ts"),
    ]);
    const offenders = sourceFiles()
      .filter((file) => !allowed.has(relative(root, file)))
      .filter((file) => /\bfetch\s*\(/.test(readFileSync(file, "utf8")))
      .map((file) => relative(root, file));
    assert.deepEqual(offenders, []);
  });

  it("keeps browser storage behind the explicit allowlist", () => {
    const storage = read("src/lib/storage.ts");
    for (const key of [
      "ce.appearance",
      "ce.theme",
      "ce.density",
      "ce.railCollapsed",
      "ce.panelWidths",
      "ce.lastRouteGroup",
    ]) {
      assert.match(storage, new RegExp(`"${key}"`));
    }
    const allowed = new Set([
      join("src", "lib", "storage.ts"),
      join("src", "features", "user-preferences", "appearanceBootstrap.ts"),
    ]);
    const offenders = sourceFiles()
      .filter((file) => !allowed.has(relative(root, file)))
      .filter((file) => /\b(localStorage|sessionStorage)\b/.test(readFileSync(file, "utf8")))
      .map((file) => relative(root, file));
    assert.deepEqual(offenders, []);
  });

  it("does not introduce browser token handling", () => {
    const combined = sourceFiles().map((file) => readFileSync(file, "utf8")).join("\n");
    for (const forbidden of ["access_token", "Authorization", "Bearer ", "sessionStorage"]) {
      assert.equal(combined.includes(forbidden), false, forbidden);
    }
  });

  it("constrains API calls to Context Engine API paths", () => {
    const client = read("src/lib/api/client.ts");
    assert.match(client, /const API_PREFIX = "\/api\/v1"/);
    assert.match(client, /\^https\?:\\\/\\\//);
    assert.match(client, /credentials: "include"/);
  });

  it("normalizes errors to the API-001 safe envelope", () => {
    const errors = read("src/lib/api/errors.ts");
    for (const field of ["code", "message", "requestId", "fields"]) {
      assert.match(errors, new RegExp(field));
    }
    assert.equal(errors.includes("raw"), false);
  });

  it("registers the Phase 1 sidebar nav order and excludes deferred surfaces", () => {
    const registry = read("src/features/navigation-sidebar/constants.ts");
    const order = ['"/chat"', '"/documents"', '"/database-visualize"'].map((href) =>
      registry.indexOf(href),
    );
    assert.deepEqual(
      [...order].sort((a, b) => a - b),
      order,
      `nav order was ${order.join(",")}`,
    );
    assert.equal(order.every((index) => index >= 0), true);
    assert.match(registry, /"\/settings"/);
    // F-010-gated LS routes must not be registered.
    for (const hidden of ['"/dashboard"', '"/logs"', '"/usage"', '"/recipes"', '"/plugins"', '"/server"']) {
      assert.equal(registry.includes(hidden), false, hidden);
    }
    const sidebar = read("src/features/navigation-sidebar/NavigationSidebar.tsx");
    assert.equal(sidebar.includes("ScrollText"), false);
    assert.equal(sidebar.includes("logs:"), false);
    assert.match(sidebar, /aria-label="Expand sidebar"/);
    assert.match(sidebar, /Logout/);
  });
});
