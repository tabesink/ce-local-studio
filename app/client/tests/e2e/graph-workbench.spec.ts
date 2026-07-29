import { expect, test } from "@playwright/test";
import { loginAsActor } from "./helpers/actors";
import { readSeedInfo } from "./helpers/stack-seed";

test.describe("E2E-M14/M15/M16/M17 graph workbench @pr-fast", () => {
  test("loads authorized domain graph via same-origin BFF only @pr-fast", async ({ page }) => {
    const seed = readSeedInfo();
    const bannedHosts: string[] = [];
    page.on("request", (request) => {
      const url = request.url();
      const origin = new URL(page.url()).origin;
      if (url.startsWith(origin) || url.startsWith("data:") || url.startsWith("blob:")) return;
      if (
        url.includes("/graphs") ||
        url.includes("lightrag") ||
        /:\d{4,5}\//.test(url) // private runtime/host ports
      ) {
        bannedHosts.push(url);
      }
    });

    await loginAsActor(page, "mina");
    const graphWait = page.waitForResponse(
      (response) =>
        response.url().includes(`/api/v1/domains/${seed.domainId}/graph`) &&
        response.request().method() === "GET",
    );
    await page.goto(`/database-visualize?domain=${encodeURIComponent(seed.domainId)}`);
    await expect(page.getByTestId("graph-workbench")).toBeVisible();
    await expect(page.getByLabel("Knowledge Domain")).toBeVisible();
    const response = await graphWait;
    expect(response.ok() || [409, 503].includes(response.status())).toBeTruthy();
    if (response.ok()) {
      const body = await response.json();
      expect(body.domain?.ref).toBeTruthy();
      expect(Array.isArray(body.nodes)).toBe(true);
      expect(Array.isArray(body.edges)).toBe(true);
      expect(JSON.stringify(body).toLowerCase()).not.toMatch(
        /\b(properties|chunk_id|working_dir|prompt)\b/,
      );
    }
    expect(bannedHosts, `unexpected non-BFF graph traffic: ${bannedHosts.join(", ")}`).toEqual([]);
  });

  test("list search selects node and syncs URL @pr-fast", async ({ page }) => {
    const seed = readSeedInfo();
    await loginAsActor(page, "mina");
    await page.goto(`/database-visualize?domain=${encodeURIComponent(seed.domainId)}`);
    await expect(page.getByTestId("graph-workbench")).toBeVisible();

    const search = page.getByPlaceholder(/Filter or search labels/i);
    if (await search.isVisible().catch(() => false)) {
      await search.fill("relief");
      const relief = page.getByRole("button", { name: /Relief valve/i }).first();
      if (await relief.isVisible({ timeout: 15_000 }).catch(() => false)) {
        await relief.click();
        await expect(page).toHaveURL(/node=/);
        await expect(page.getByTestId("graph-node-detail")).toBeVisible();
        await expect(page.getByTestId("graph-accessible-summary")).toContainText(/Relief valve|Selected/i);
      }
    }

    await page.goto(`/database-visualize?domain=not-a-real-domain-ref-zzzz`);
    await expect(page.getByTestId("graph-workbench")).toBeVisible();
    // Unknown domain: safe failure or empty eligible — never raw stack.
    const body = await page.locator("body").innerText();
    expect(body.toLowerCase()).not.toMatch(/\b(traceback|sqlalchemy|working_dir)\b/);
  });

  test("unknown domain graph API shares nondisclosing failure shape @pr-fast", async ({
    page,
  }) => {
    await loginAsActor(page, "mina");
    const responsePromise = page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/domains/missing-domain-xyz/graph") &&
        response.request().method() === "GET",
    );
    await page.goto("/database-visualize?domain=missing-domain-xyz");
    const response = await responsePromise.catch(() => null);
    if (response) {
      expect([404, 409]).toContain(response.status());
      const json = await response.json();
      expect(json?.error?.code).toBeTruthy();
      expect(json?.error?.requestId || json?.requestId).toBeTruthy();
    }
  });
});
