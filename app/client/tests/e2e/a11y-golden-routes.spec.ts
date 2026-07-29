import { expect, test } from "@playwright/test";
import { loginAsActor } from "./helpers/actors";
import { expectNoCriticalAxeViolations } from "./helpers/a11y";
import { logout, sendChatMessage } from "./helpers/auth";
import { E2E_DOMAIN_QUESTION, readSeedInfo } from "./helpers/stack-seed";

test.describe("E2E a11y golden routes @pr-fast", () => {
  test("login surface has no critical/serious axe violations @pr-fast", async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    try {
      await page.goto("/login");
      await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
      await expectNoCriticalAxeViolations(page, "login");
    } finally {
      await context.close();
    }
  });

  test("Mina chat + graph + settings + logout keyboard path @pr-fast", async ({ page }) => {
    test.setTimeout(300_000);
    const seed = readSeedInfo();
    await loginAsActor(page, "mina");

    await expect(page.getByRole("main")).toBeVisible();
    await expectNoCriticalAxeViolations(page, "chat-shell");

    await page.getByLabel("Knowledge Domain").selectOption({ label: seed.displayName });
    await sendChatMessage(page, E2E_DOMAIN_QUESTION);
    await expect(page.getByTestId("chat-streaming")).toHaveAttribute("data-streaming", "false", {
      timeout: 180_000,
    });
    const evidence = page.getByRole("complementary", { name: "Evidence" });
    if (await evidence.isVisible().catch(() => false)) {
      const first = evidence.getByRole("listitem").first();
      if (await first.isVisible().catch(() => false)) {
        await first.focus();
        await page.keyboard.press("Enter");
      }
      await expectNoCriticalAxeViolations(page, "chat-evidence");
    }

    await page.goto(`/database-visualize?domain=${encodeURIComponent(seed.domainId)}`);
    await expect(page.getByTestId("graph-workbench")).toBeVisible();
    await expectNoCriticalAxeViolations(page, "graph-workbench");

    const search = page.getByPlaceholder(/Filter or search labels/i);
    if (await search.isVisible().catch(() => false)) {
      await search.focus();
      await search.fill("relief");
      await page.keyboard.press("Tab");
      const relief = page.getByRole("button", { name: /Relief valve/i }).first();
      if (await relief.isVisible({ timeout: 10_000 }).catch(() => false)) {
        await relief.focus();
        await page.keyboard.press("Enter");
        await expect(page.getByTestId("graph-node-detail")).toBeVisible();
        await expect(page).toHaveURL(/node=/);
      }
    }
    await expectNoCriticalAxeViolations(page, "graph-selected");

    await page.goto("/documents");
    await expect(page.getByRole("main")).toBeVisible();
    await expectNoCriticalAxeViolations(page, "documents");

    await page.goto("/settings?section=domains");
    await expect(page.getByRole("main")).toBeVisible();
    await expectNoCriticalAxeViolations(page, "settings-domains");

    await logout(page);
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
    await expectNoCriticalAxeViolations(page, "login-after-logout");
  });

  test("Ava settings domains axe @pr-fast", async ({ page }) => {
    await loginAsActor(page, "ava");
    await page.goto("/settings?section=domains");
    await expect(page.getByRole("main")).toBeVisible();
    await expectNoCriticalAxeViolations(page, "admin-settings-domains");
  });
});
