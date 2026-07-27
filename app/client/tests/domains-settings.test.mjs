import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

async function loadTsModule(relativePath) {
  const ts = await import("typescript");
  const source = readFileSync(join(root, relativePath), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
      verbatimModuleSyntax: true,
    },
  });
  return import(`data:text/javascript;charset=utf-8,${encodeURIComponent(outputText)}`);
}

function read(relativePath) {
  return readFileSync(join(root, relativePath), "utf8");
}

async function loadHelpers() {
  return loadTsModule("src/features/settings-panel/domainSettingsHelpers.ts");
}

describe("Domain settings helpers (F-009 deploy)", () => {
  it("accepts and rejects domain ids per backend slug pattern", async () => {
    const { isValidDomainId } = await loadHelpers();

    assert.equal(isValidDomainId("ab"), true);
    assert.equal(isValidDomainId("fatigue"), true);
    assert.equal(isValidDomainId("ops-notes"), true);
    assert.equal(isValidDomainId("a_b"), true);
    assert.equal(isValidDomainId("a1"), true);

    assert.equal(isValidDomainId(""), false);
    assert.equal(isValidDomainId("a"), false);
    assert.equal(isValidDomainId("-ab"), false);
    assert.equal(isValidDomainId("Ab"), false);
    assert.equal(isValidDomainId("has space"), false);
    assert.equal(isValidDomainId("a".repeat(64)), false);
  });

  it("filters embedding profiles and prefers isDefault", async () => {
    const { filterEmbeddingProfiles, defaultEmbeddingProfileId, canDeployDomain } = await loadHelpers();

    const profiles = [
      { id: "syn", name: "Synth", profileKind: "synthesis", isDefault: true },
      { id: "emb-a", name: "Emb A", profileKind: "embedding", isDefault: false },
      { id: "emb-b", name: "Emb B", profileKind: "embedding", isDefault: true },
    ];

    const embedding = filterEmbeddingProfiles(profiles);
    assert.deepEqual(
      embedding.map((p) => p.id),
      ["emb-a", "emb-b"],
    );
    assert.equal(defaultEmbeddingProfileId(profiles), "emb-b");
    assert.equal(defaultEmbeddingProfileId([{ id: "x", profileKind: "synthesis", isDefault: true }]), null);

    assert.equal(
      canDeployDomain({
        id: "ops-notes",
        displayName: "Ops",
        embeddingProfileId: "emb-b",
        hasEmbeddingProfiles: true,
      }),
      true,
    );
    assert.equal(
      canDeployDomain({
        id: "ops-notes",
        displayName: "Ops",
        embeddingProfileId: "emb-b",
        hasEmbeddingProfiles: false,
      }),
      false,
    );
    assert.equal(
      canDeployDomain({
        id: "X",
        displayName: "Ops",
        embeddingProfileId: "emb-b",
        hasEmbeddingProfiles: true,
      }),
      false,
    );
    assert.equal(
      canDeployDomain({
        id: "ops-notes",
        displayName: "  ",
        embeddingProfileId: "emb-b",
        hasEmbeddingProfiles: true,
      }),
      false,
    );
  });

  it("deployDomain: success, create_failed, and start_failed_keep without delete", async () => {
    const { deployDomain } = await loadHelpers();

    const successCalls = { create: 0, start: 0, delete: 0 };
    const success = await deployDomain(
      { id: "ops-notes", displayName: "Ops Notes", embeddingProfileId: "emb-1" },
      {
        createDomain: async (input) => {
          successCalls.create += 1;
          assert.equal(input.id, "ops-notes");
          return { id: input.id };
        },
        startDomain: async (domainId) => {
          successCalls.start += 1;
          assert.equal(domainId, "ops-notes");
        },
      },
    );
    assert.equal(success.kind, "success");
    assert.deepEqual(successCalls, { create: 1, start: 1, delete: 0 });

    const createFail = await deployDomain(
      { id: "ops-notes", displayName: "Ops", embeddingProfileId: "emb-1" },
      {
        createDomain: async () => {
          throw new Error("create blocked");
        },
        startDomain: async () => {
          throw new Error("start should not run");
        },
      },
    );
    assert.equal(createFail.kind, "create_failed");
    assert.equal(createFail.error instanceof Error && createFail.error.message, "create blocked");

    let startCalled = false;
    const startFail = await deployDomain(
      { id: "kept", displayName: "Kept", embeddingProfileId: "emb-1" },
      {
        createDomain: async () => ({ id: "kept" }),
        startDomain: async () => {
          startCalled = true;
          throw new Error("start failed");
        },
      },
    );
    assert.equal(startCalled, true);
    assert.equal(startFail.kind, "start_failed_keep");
    assert.equal(startFail.error instanceof Error && startFail.error.message, "start failed");
  });

  it("maps busy labels and Start XOR Stop from state", async () => {
    const { busyLabel, primaryLifecycleAction, domainTone, shouldRequestDelete } = await loadHelpers();

    assert.equal(busyLabel("start"), "starting");
    assert.equal(busyLabel("stop"), "stopping");
    assert.equal(busyLabel("delete"), "deleting");
    assert.equal(busyLabel("deploy"), "deploying");

    assert.equal(primaryLifecycleAction("running"), "stop");
    assert.equal(primaryLifecycleAction("stopped"), "start");
    assert.equal(primaryLifecycleAction("error"), "start");
    assert.equal(primaryLifecycleAction("deleting"), null);

    assert.equal(domainTone("running"), "good");
    assert.equal(domainTone("error"), "danger");
    assert.equal(domainTone("stopped"), "default");

    assert.equal(shouldRequestDelete(false), false);
    assert.equal(shouldRequestDelete(true), true);
  });

  it("formats backend-owned storage summaries", async () => {
    const { clampStoragePercent, formatBytes, storageLimitLabel, storageTone, storageWarningLabel } =
      await loadHelpers();

    assert.equal(formatBytes(0), "0 B");
    assert.equal(formatBytes(512), "512 B");
    assert.equal(formatBytes(2048), "2 KB");
    assert.equal(formatBytes(1536 * 1024), "1.5 MB");
    assert.equal(formatBytes(5 * 1024 * 1024 * 1024), "5 GB");

    assert.equal(clampStoragePercent(-1), 0);
    assert.equal(clampStoragePercent(0.4), 1);
    assert.equal(clampStoragePercent(12.6), 13);
    assert.equal(clampStoragePercent(140), 100);

    const summary = {
      totalBytes: 1024,
      limitBytes: 5 * 1024,
      totalPercent: 20,
      warning: "near_limit",
      components: [],
    };
    assert.equal(storageLimitLabel(summary), "1 KB of 5 KB");
    assert.equal(storageTone("ok"), "default");
    assert.equal(storageTone("near_limit"), "warning");
    assert.equal(storageTone("exceeded"), "danger");
    assert.equal(storageWarningLabel("ok"), "ok");
    assert.equal(storageWarningLabel("near_limit"), "near limit");
    assert.equal(storageWarningLabel("exceeded"), "exceeded");
  });

  it("maps embedding labels and accordion expand toggle", async () => {
    const { embeddingProfileLabel, nextExpandedDomainId } = await loadHelpers();

    const profiles = [
      { id: "emb-a", name: "Emb A", profileKind: "embedding", isDefault: false },
      { id: "emb-b", name: "  Emb B  ", profileKind: "embedding", isDefault: true },
    ];

    assert.equal(embeddingProfileLabel("emb-b", profiles), "Emb B");
    assert.equal(embeddingProfileLabel("missing", profiles), "missing");
    assert.equal(embeddingProfileLabel("", profiles), "Locked");
    assert.equal(embeddingProfileLabel(null, profiles), "Locked");

    assert.equal(nextExpandedDomainId(null, "a"), "a");
    assert.equal(nextExpandedDomainId("a", "a"), null);
    assert.equal(nextExpandedDomainId("a", "b"), "b");
  });

  it("Domains Settings UI uses UiModal delete, accordion, and omits operator field tokens", async () => {
    const { FORBIDDEN_DOMAIN_UI_FIELD_TOKENS } = await loadHelpers();

    const panel = read("src/features/settings-panel/SettingsPanel.tsx");
    const sharedUi = read("src/_shared/ui/index.tsx");
    const domainsApi = read("src/features/domains/api.ts");

    assert.match(panel, /from "@\/components\/ui"/);
    assert.match(panel, /UiModal/);
    assert.match(panel, /IconButton/);
    assert.match(panel, /Input/);
    assert.match(panel, /Select/);
    assert.doesNotMatch(panel, /ProgressBar/);
    assert.match(panel, /Knowledge Domains/);
    assert.match(panel, /New Knowledge Domain/);
    assert.doesNotMatch(panel, /LightRAG Containers/);
    assert.match(panel, /deployDomain/);
    assert.match(panel, /Deploy/);
    assert.match(panel, /ChevronDown/);
    assert.match(panel, /aria-expanded/);
    assert.match(panel, /ToggleSwitch/);
    assert.match(panel, /checked=\{lifecycle === "stop"\}/);
    assert.match(panel, /embeddingProfile\.name/);
    assert.match(panel, /nextExpandedDomainId/);
    assert.doesNotMatch(panel, /storageLimitLabel/);
    assert.doesNotMatch(panel, /storageWarningLabel/);
    assert.doesNotMatch(panel, /storageSummary/);
    assert.match(panel, /· locked/);
    assert.match(panel, /Embedding model/);
    assert.doesNotMatch(panel, /window\.confirm/);

    assert.match(panel, /flex flex-wrap items-center gap-2 px-3\.5 py-2\.5/);
    assert.doesNotMatch(panel, /flex flex-col gap-2 px-3\.5 py-3/);
    assert.doesNotMatch(panel, /data-testid="domain-storage-summary"/);
    assert.doesNotMatch(panel, /data-testid="domain-storage-total-bar"/);
    assert.doesNotMatch(panel, /role="meter"/);
    assert.doesNotMatch(panel, /aria-valuetext/);
    assert.doesNotMatch(panel, /<select/);
    assert.match(sharedUi, /tone === "warning"[\s\S]*bg-\(--ui-warning\)/);
    assert.match(sharedUi, /tone === "danger"[\s\S]*bg-\(--ui-danger\)/);

    // Create/deploy lives in its own SettingsGroup card below the accordion list.
    const listGroupEnd = panel.indexOf('title="New Knowledge Domain"');
    assert.ok(listGroupEnd > 0, "New Knowledge Domain card must exist");
    const accordionCard = panel.slice(panel.indexOf('title="Knowledge Domains"'), listGroupEnd);
    assert.doesNotMatch(accordionCard, /Deploying|onDeploy|draftName/);
    assert.doesNotMatch(accordionCard, />Name<\/span>|>Id<\/span>/);
    assert.doesNotMatch(accordionCard, /storageSummary/);
    assert.match(panel.slice(listGroupEnd), /draftName|onDeploy|Deploy/);

    const collapsedHeader = panel.slice(
      panel.indexOf('className="flex items-center gap-3 px-3.5 py-2.5'),
      panel.indexOf("{expanded ? ("),
    );
    assert.doesNotMatch(collapsedHeader, /storageSummary|domain-storage-summary|Storage/);
    assert.doesNotMatch(collapsedHeader, />\s*Delete\s*</);
    assert.match(panel.slice(panel.indexOf("{expanded ? ("), listGroupEnd), />\s*Delete\s*</);

    // DomainsSection should not render both Start and Stop on the same row template
    assert.match(panel, /primaryLifecycleAction/);

    // Scan Domains UI surface only — helpers may list forbidden tokens for this guard.
    for (const token of FORBIDDEN_DOMAIN_UI_FIELD_TOKENS) {
      assert.equal(
        panel.includes(token),
        false,
        `Domains Settings UI must not include operator field token ${token}`,
      );
    }

    // Safe admin DTO fields remain the client seam — no infra keys / storageSummary on AdminDomain
    assert.match(domainsApi, /export type AdminDomain/);
    assert.doesNotMatch(domainsApi, /storageSummary/);
    for (const token of ["hostPort", "host_port", "containerId", "runtimeUrl", "baseUrl"]) {
      assert.equal(domainsApi.includes(token), false, `AdminDomain API must not expose ${token}`);
    }
  });
});
