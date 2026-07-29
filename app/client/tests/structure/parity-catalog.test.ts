import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const clientRoot = new URL("../..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const repoRoot = join(clientRoot, "..", "..");
const parityRoot = join(clientRoot, "tests", "parity");
const manifestsRoot = join(parityRoot, "manifests");

const REQUIRED_TARGETS = [
  "app-shell",
  "button",
  "card",
  "chat-workbench",
  "checkbox",
  "composer",
  "confirm-action-dialog",
  "conversation-rail",
  "document-library",
  "document-viewer",
  "domains-accordion",
  "drawer",
  "error-box",
  "evidence-inspector",
  "graph-workbench",
  "input",
  "list-row",
  "login",
  "markdown-content",
  "navigation-rail",
  "operation-status",
  "page-state",
  "pane-header",
  "provider-settings",
  "resource-table",
  "right-inspector",
  "segmented-control",
  "select",
  "settings-group",
  "settings-nav",
  "settings-row",
  "skeleton",
  "source-operation-panel",
  "status-pill",
  "table",
  "tabs",
  "textarea",
  "toggle-switch",
  "transcript",
  "ui-modal",
] as const;

type Manifest = {
  schemaVersion: number;
  targetId: string;
  owner: string;
  layer: "primitive" | "shared" | "feature";
  catalogState: "FACTORY_READY";
  disposition: string;
  htmlStatic: {
    forbiddenClaims: string[];
  };
};

function readManifest(targetId: string): Manifest {
  return JSON.parse(
    readFileSync(join(manifestsRoot, `${targetId}.json`), "utf8"),
  ) as Manifest;
}

describe("full workstation HTML parity catalog", () => {
  it("contains exactly the required Phase 1 target register", () => {
    const actual = readdirSync(manifestsRoot)
      .filter((entry) => entry.endsWith(".json"))
      .map((entry) => entry.replace(/\.json$/, ""))
      .sort();
    assert.deepEqual(actual, [...REQUIRED_TARGETS].sort());
  });

  it("requires a valid manifest, script-free HTML, and React proof for every target", () => {
    for (const targetId of REQUIRED_TARGETS) {
      const manifestPath = join(manifestsRoot, `${targetId}.json`);
      const fixturePath = join(parityRoot, "fixtures", `${targetId}.html`);
      const reactPath = join(parityRoot, "react", `${targetId}.test.tsx`);
      assert.equal(existsSync(manifestPath), true, `missing manifest: ${targetId}`);
      assert.equal(existsSync(fixturePath), true, `missing HTML fixture: ${targetId}`);
      assert.equal(existsSync(reactPath), true, `missing React proof: ${targetId}`);

      const manifest = readManifest(targetId);
      assert.equal(manifest.schemaVersion, 1, `${targetId}: schemaVersion`);
      assert.equal(manifest.targetId, targetId, `${targetId}: targetId`);
      assert.ok(["primitive", "shared", "feature"].includes(manifest.layer), `${targetId}: layer`);
      assert.equal(manifest.catalogState, "FACTORY_READY", `${targetId}: catalogState`);
      assert.ok(manifest.owner.length > 0, `${targetId}: owner`);
      assert.ok(manifest.disposition.length > 0, `${targetId}: disposition`);
      for (const claim of ["focus", "ARIA", "keyboard", "touch", "state-transition"]) {
        assert.ok(
          manifest.htmlStatic.forbiddenClaims.includes(claim),
          `${targetId}: HTML must disclaim ${claim}`,
        );
      }

      const html = readFileSync(fixturePath, "utf8");
      assert.match(html, /Not product authority/i, `${targetId}: authority warning`);
      assert.doesNotMatch(html, /<script\b/i, `${targetId}: fixtures must be script-free`);
      assert.doesNotMatch(
        html,
        /\b(?:https?:\/\/|s3:\/\/|file:\/\/|\/var\/|\/home\/)\S*/i,
        `${targetId}: fixtures must be network/path-free`,
      );
    }
  });

  it("keeps the normative documentation register synchronized", () => {
    const paritySpec = readFileSync(join(repoRoot, "docs", "frontend", "ui-parity-spec.md"), "utf8");
    for (const targetId of REQUIRED_TARGETS) {
      assert.match(
        paritySpec,
        new RegExp(String.raw`\|\s*${targetId}\s*\|[^\n]*\|\s*FACTORY_READY\s*\|`),
        `${targetId}: missing FACTORY_READY documentation row`,
      );
    }
  });

  it("keeps the local gallery non-routable and complete", () => {
    const indexPath = join(parityRoot, "index.html");
    assert.equal(existsSync(indexPath), true, "missing tests/parity/index.html");
    const index = readFileSync(indexPath, "utf8");
    assert.doesNotMatch(index, /<script\b/i, "gallery index must be script-free");
    for (const targetId of REQUIRED_TARGETS) {
      assert.match(index, new RegExp(`fixtures/${targetId}\\.html`), `${targetId}: missing index link`);
    }
    assert.equal(
      existsSync(join(clientRoot, "src", "app", "parity")),
      false,
      "gallery must not be a product route",
    );
  });
});
