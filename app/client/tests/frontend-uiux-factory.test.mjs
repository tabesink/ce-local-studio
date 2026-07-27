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
];

describe("frontend factory authority", () => {
  it("requires the canonical frontend contract package and subordinate factory plan", () => {
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
  });

  it("defines one eventual primitive home and treats lifted kits as migration inventory", () => {
    const agents = readRepo("docs/frontend/AGENTS.md");
    const components = readRepo("docs/frontend/component-contracts.md");
    assert.match(agents, /product-neutral primitives in `src\/ui`/);
    assert.match(agents, /Temporary legacy import specifiers/);
    assert.match(components, /src\/ui contains API-free, router-free, product-neutral primitives/);
    assert.match(components, /create a second component tree under src\/components/);
  });

  it("keeps the starter factory bounded and the Domain accordion amendment in progress", () => {
    const agents = readRepo("docs/frontend/AGENTS.md");
    const plan = readRepo("docs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md");
    const parity = readRepo("docs/frontend/ui-parity-spec.md");
    assert.match(agents, /Button, Input, StatusPill, SettingsRow/);
    assert.match(agents, /catalog state is `IN_PROGRESS` until parity evidence earns `FACTORY_READY`/);
    assert.match(agents, /starter coverage, not a complete allowlist/);
    assert.match(parity, /Settings Domain accordion[\s\S]*IN_PROGRESS/);
    assert.doesNotMatch(parity, /Settings Domain accordion[\s\S]*BLOCKED_CONTRACT/);
    assert.match(plan, /phase_compatibility: phase-1-child/);
    assert.match(plan, /no application factory is considered shipped during D0/);
    assert.match(plan, /live `\/settings\?section=domains` proof must use contracted DTO\/BFF states/);
  });
});
