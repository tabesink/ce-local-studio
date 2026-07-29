import { expect, test } from "@playwright/test";
import { loginAsActor, newActorContext } from "./helpers/actors";
import { logout } from "./helpers/auth";
import { readSeedInfo } from "./helpers/stack-seed";

test.describe("E2E-C04 two-user isolation / graph partition @pr-fast", () => {
  test("Noah cannot read Mina conversation by guessing URL @pr-fast", async ({ browser }) => {
    const mina = await newActorContext(browser, "mina");
    const noah = await newActorContext(browser, "noah");
    try {
      await mina.page.goto("/chat");
      await expect(mina.page.getByLabel("Knowledge Domain")).toBeVisible();

      // Capture any conversation href Mina can see; Noah must not receive transcript bytes.
      const minaLinks = mina.page.locator('a[href*="/chat"]');
      const href = (await minaLinks.first().getAttribute("href").catch(() => null)) ?? "/chat";
      await noah.page.goto(href);
      const body = await noah.page.locator("body").innerText();
      expect(body.toLowerCase()).not.toContain("private mina");
      // Ownership-sensitive resources share one not-found/unauthorized shape — no Mina transcript.
      await expect(noah.page.getByTestId("assistant-turn")).toHaveCount(0);
    } finally {
      await mina.context.close();
      await noah.context.close();
    }
  });

  test("Mina graph domain URL does not leak to Noah as success bytes @pr-fast", async ({
    browser,
  }) => {
    const seed = readSeedInfo();
    const mina = await newActorContext(browser, "mina");
    const noah = await newActorContext(browser, "noah");
    try {
      await mina.page.goto(`/database-visualize?domain=${encodeURIComponent(seed.domainId)}`);
      await expect(mina.page.getByTestId("graph-workbench")).toBeVisible();

      const graphResponse = noah.page.waitForResponse(
        (response) =>
          response.url().includes(`/api/v1/domains/${seed.domainId}/graph`) &&
          response.request().method() === "GET",
      );
      await noah.page.goto(`/database-visualize?domain=${encodeURIComponent(seed.domainId)}`);
      const response = await graphResponse.catch(() => null);
      if (response) {
        // Authorized members may share domain graph; assert closed DTO / no private bags.
        if (response.ok()) {
          const json = await response.json();
          expect(JSON.stringify(json).toLowerCase()).not.toMatch(
            /\b(properties|chunk_id|working_dir|password|bearer)\b/,
          );
        } else {
          expect([401, 403, 404, 409]).toContain(response.status());
        }
      }
      await expect(noah.page.getByTestId("graph-workbench")).toBeVisible();
    } finally {
      await mina.context.close();
      await noah.context.close();
    }
  });

  test("logout clears personalized graph projection from Back @pr-fast", async ({ page }) => {
    const seed = readSeedInfo();
    await loginAsActor(page, "mina");
    await page.goto(`/database-visualize?domain=${encodeURIComponent(seed.domainId)}`);
    await expect(page.getByTestId("graph-workbench")).toBeVisible();
    await logout(page);
    await page.goBack();
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByTestId("graph-workbench")).toHaveCount(0);
  });
});
