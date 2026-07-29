import fs from "node:fs";
import path from "node:path";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { loginAsActor } from "./helpers/actors";
import { sendChatMessage } from "./helpers/auth";
import { applyTheme, freezeForScreenshot, type Theme } from "./helpers/theme";
import { E2E_DOMAIN_QUESTION, readSeedInfo } from "./helpers/stack-seed";

type ManifestEntry = {
  id: string;
  lane: "pr-fast" | "release";
  targetId: string | null;
  route: string;
  persona: string;
  state: string;
  viewport: { width: number; height: number };
  theme: Theme;
  expectedPath: string;
  masks: string[];
  maxDiffPixelRatio: number;
  approvalStatus: string;
};

type Manifest = {
  schemaVersion: string;
  maxDiffPixelRatio: number;
  entries: ManifestEntry[];
};

const MANIFEST_PATH = path.resolve(__dirname, "visual-parity-manifest.json");
const BASE_DIR = path.resolve(__dirname);

function loadManifest(): Manifest {
  return JSON.parse(fs.readFileSync(MANIFEST_PATH, "utf8")) as Manifest;
}

function approvedEntries(lane: "pr-fast" | "release"): ManifestEntry[] {
  return loadManifest().entries.filter(
    (e) =>
      e.lane === lane &&
      (e.approvalStatus === "approved" || e.approvalStatus === "diverged_approved"),
  );
}

async function maskLocators(page: Page, masks: string[]): Promise<Locator[]> {
  const out: Locator[] = [];
  for (const name of masks) {
    if (name === "graph-canvas") {
      const loc = page.getByTestId("graph-canvas");
      if (await loc.count()) out.push(loc);
    }
  }
  return out;
}

async function captureApproved(page: Page, entry: ManifestEntry) {
  const baselineAbs = path.join(BASE_DIR, entry.expectedPath);
  expect(
    fs.existsSync(baselineAbs),
    `missing baseline for approved entry ${entry.id}: ${entry.expectedPath}`,
  ).toBeTruthy();

  await page.setViewportSize(entry.viewport);
  await applyTheme(page, entry.theme);
  await freezeForScreenshot(page);
  const mask = await maskLocators(page, entry.masks);
  await expect(page).toHaveScreenshot(path.basename(entry.expectedPath), {
    maxDiffPixelRatio: entry.maxDiffPixelRatio,
    fullPage: false,
    mask,
    // Playwright stores under test file snapshot dir; we also require the
    // committed path listed in the manifest to exist (fail-closed).
  });
}

test.describe("visual parity gate + compare", () => {
  test("manifest schema is present and lists graph-workbench targetIds @pr-fast", async () => {
    const manifest = loadManifest();
    expect(manifest.schemaVersion).toBe("1.0");
    expect(manifest.maxDiffPixelRatio).toBeLessThanOrEqual(0.005);
    const graph = manifest.entries.filter((e) => e.route.includes("database-visualize"));
    expect(graph.length).toBeGreaterThan(0);
    for (const entry of graph) {
      expect(entry.targetId).toBe("graph-workbench");
    }
  });

  test("PR-fast toHaveScreenshot compare for approved baselines @pr-fast", async ({
    browser,
    page,
  }) => {
    const entries = approvedEntries("pr-fast");
    test.skip(
      entries.length === 0,
      "No approved PR-fast visual baselines yet — run capture then set approvalStatus=approved. Enforce gate: python app/scripts/verify_visual_parity_manifest.py enforce --lane pr-fast",
    );
    test.setTimeout(300_000);

    const loginEntries = entries.filter((e) => e.route === "/login");
    if (loginEntries.length) {
      const loginContext = await browser.newContext();
      const loginPage = await loginContext.newPage();
      try {
        await loginPage.goto("/login");
        await expect(loginPage.locator("#username")).toBeVisible();
        for (const entry of loginEntries) {
          await captureApproved(loginPage, entry);
        }
      } finally {
        await loginContext.close();
      }
    }

    const seed = readSeedInfo();
    const needsMina = entries.some((e) => e.persona.includes("mina") || e.route === "/chat");
    const needsAva = entries.some((e) => e.persona.includes("ava"));

    if (needsMina) {
      await loginAsActor(page, "mina");
      const chatEntries = entries.filter((e) => e.route === "/chat");
      if (chatEntries.length) {
        await page.getByLabel("Knowledge Domain").selectOption({ label: seed.displayName });
        await sendChatMessage(page, E2E_DOMAIN_QUESTION);
        const evidence = page.getByRole("complementary", { name: "Evidence" });
        await expect(evidence).toBeVisible({ timeout: 120_000 });
        for (const entry of chatEntries) {
          await captureApproved(page, entry);
        }
      }

      const graphEntries = entries.filter((e) => e.route.includes("database-visualize"));
      for (const entry of graphEntries) {
        await page.goto(`/database-visualize?domain=${encodeURIComponent(seed.domainId)}`);
        await expect(page.getByTestId("graph-workbench")).toBeVisible();
        if (entry.state === "selected-node") {
          const search = page.getByPlaceholder(/Filter or search labels/i);
          if (await search.isVisible().catch(() => false)) {
            await search.fill("relief");
            const relief = page.getByRole("button", { name: /Relief valve/i }).first();
            if (await relief.isVisible({ timeout: 15_000 }).catch(() => false)) {
              await relief.click();
              await expect(page.getByTestId("graph-node-detail")).toBeVisible();
            }
          }
        }
        await captureApproved(page, entry);
      }
    }

    if (needsAva) {
      const ava = await browser.newContext();
      const avaPage = await ava.newPage();
      try {
        await loginAsActor(avaPage, "ava");
        for (const entry of entries.filter((e) => e.route.startsWith("/settings"))) {
          await avaPage.goto(entry.route);
          await expect(avaPage.getByRole("main")).toBeVisible();
          await captureApproved(avaPage, entry);
        }
      } finally {
        await ava.close();
      }
    }
  });

  test("release visual matrix compare when approved @release", async ({ page }) => {
    const entries = approvedEntries("release");
    test.skip(entries.length === 0, "No approved @release visual baselines yet");
    test.setTimeout(300_000);
    const seed = readSeedInfo();
    await loginAsActor(page, "mina");
    for (const entry of entries) {
      if (entry.route.includes("database-visualize")) {
        await page.goto(`/database-visualize?domain=${encodeURIComponent(seed.domainId)}`);
        await expect(page.getByTestId("graph-workbench")).toBeVisible();
        await captureApproved(page, entry);
      }
    }
  });
});
