import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const repoRoot = join(root, "..", "..");

function readRepo(relativePath) {
  return readFileSync(join(repoRoot, relativePath), "utf8");
}

const REQUIRED_FILES = [
  "DESIGN.md",
  "docs/frontend/AGENTS.md",
  "docs/frontend/accessibility-contract.md",
  "docs/frontend/component-contracts.md",
  "docs/frontend/design-token-contract.md",
  "docs/frontend/route-and-workspace-spec.md",
  "docs/frontend/ui-parity-spec.md",
  "docs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md",
  "docs/plans/2026-07-28-002-feat-full-workstation-html-gallery-plan.md",
];

const STARTER_MANIFESTS = [
  ["button", "primitive"],
  ["input", "primitive"],
  ["status-pill", "primitive"],
  ["settings-row", "feature"],
  ["domains-accordion", "feature"],
];

describe("frontend factory authority", () => {
  it("requires the canonical frontend contract package and Option A gallery plan", () => {
    for (const relativePath of REQUIRED_FILES) {
      assert.equal(
        existsSync(join(repoRoot, relativePath)),
        true,
        `missing required frontend authority file: ${relativePath}`,
      );
    }
  });

  it("keeps visual guidance subordinate to product and contract authority", () => {
    const design = readRepo("DESIGN.md");
    assert.match(design, /subordinate visual guidance/);
    assert.match(
      design,
      /Product, security, accessibility, route\/state, DTO, and component contracts take precedence/,
    );
    assert.match(design, /Local Studio remains read-only evidence/);
    assert.match(design, /Option A \(P9-06\)/);
    assert.match(design, /Compose only from targets that have HTML fixtures/);
  });

  it("defines one eventual primitive home and treats lifted kits as migration inventory", () => {
    const agents = readRepo("docs/frontend/AGENTS.md");
    const components = readRepo("docs/frontend/component-contracts.md");
    assert.match(agents, /product-neutral primitives in `src\/ui`/);
    assert.match(agents, /Temporary legacy import specifiers/);
    assert.match(components, /src\/ui contains API-free, router-free, product-neutral primitives/);
    assert.match(components, /create a second component tree under src\/components/);
  });

  it("requires Option A full workstation HTML gallery compose-from-catalog rule", () => {
    const agents = readRepo("docs/frontend/AGENTS.md");
    const parity = readRepo("docs/frontend/ui-parity-spec.md");
    const master = readRepo("docs/master-build-plan.md");
    const visual = readRepo("docs/frontend/visual-regression-plan.md");
    const factory = readRepo("docs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md");

    assert.match(agents, /Option A — full workstation gallery/);
    assert.match(agents, /Compose only from catalog targets that have script-free HTML fixtures/);
    assert.match(agents, /Missing target → stop and amend the catalog/);
    assert.match(agents, /FACTORY_READY[\s\S]*Vitest\/RTL|five-starter subset[\s\S]*FACTORY_READY/);
    assert.match(agents, /P11-04 Evidence attach\/suggest gallery targets while that work is DEFERRED/);

    assert.match(parity, /Phase 1 workstation factory catalog/);
    assert.match(parity, /Option A rule/);
    assert.match(parity, /Full Phase 1 register/);
    assert.match(parity, /conversation-rail/);
    assert.match(parity, /transcript/);
    assert.match(parity, /composer/);
    assert.match(parity, /evidence-inspector/);
    assert.match(parity, /P9-06/);
    assert.match(parity, /Settings Domain accordion[\s\S]*FACTORY_READY|domains-accordion[\s\S]*FACTORY_READY/);
    assert.doesNotMatch(parity, /Settings Domain accordion[\s\S]*BLOCKED_CONTRACT/);
    assert.doesNotMatch(
      parity,
      /Uncovered roles continue using the contracted canonical CE control; agents record a parity gap/,
    );

    assert.match(master, /\| P9-06 \|/);
    assert.match(master, /Option A full workstation HTML gallery/);
    assert.match(visual, /catalog `targetId`s/);
    assert.match(factory, /Superseded for gallery scope \(P9-06/);
    assert.match(factory, /phase_compatibility: phase-1-child/);
    assert.match(factory, /no application factory is considered shipped during D0/);
    assert.match(factory, /live `\/settings\?section=domains` proof must use contracted DTO\/BFF states/);
  });

  it("backfills layer on starter manifests", () => {
    for (const [targetId, layer] of STARTER_MANIFESTS) {
      const relativePath = `app/client/tests/parity/manifests/${targetId}.json`;
      assert.equal(existsSync(join(repoRoot, relativePath)), true, `missing ${relativePath}`);
      const manifest = JSON.parse(readRepo(relativePath));
      assert.equal(manifest.targetId, targetId);
      assert.equal(manifest.layer, layer, `${targetId} layer`);
      assert.equal(manifest.catalogState, "FACTORY_READY");
      assert.equal(manifest.schemaVersion, 1);
    }
  });
});
