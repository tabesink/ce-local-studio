import { expect, test } from "@playwright/test";
import { loginAsAdmin, logout, sendChatMessage } from "./helpers/auth";
import { assertNoAuthTokensInBrowserStorage } from "./helpers/storage";
import {
  E2E_DIRECT_QUESTION,
  E2E_DOMAIN_QUESTION,
  readSeedInfo,
} from "./helpers/stack-seed";

test.describe.configure({ mode: "serial" });

async function waitForStreamSettled(page: import("@playwright/test").Page) {
  const assistant = page.getByTestId("assistant-turn").last();
  await expect(assistant).toBeVisible({ timeout: 90_000 });
  await expect(page.getByTestId("chat-streaming")).toHaveAttribute("data-streaming", "false", {
    timeout: 90_000,
  });
  await expect(assistant).not.toContainText("Streaming...");
  return assistant;
}

test.describe("F-009 pilot happy path", () => {
  test("login, storage safety, and logout", async ({ page }) => {
    await loginAsAdmin(page);
    await assertNoAuthTokensInBrowserStorage(page);
    await logout(page);
    await expect(page.locator("#username")).toBeVisible();
  });

  test("direct chat leaves Evidence Panel without rows", async ({ page }) => {
    await loginAsAdmin(page);
    await page.getByLabel("Knowledge Domain").selectOption({ label: "Direct chat" });
    await sendChatMessage(page, E2E_DIRECT_QUESTION);

    await expect(page.getByText(E2E_DIRECT_QUESTION)).toBeVisible();
    const assistant = await waitForStreamSettled(page);
    await expect(assistant.locator(".whitespace-pre-wrap").first()).not.toBeEmpty();

    const evidence = page.getByRole("complementary", { name: "Evidence" });
    if (await evidence.isVisible().catch(() => false)) {
      await expect(evidence.getByRole("listitem")).toHaveCount(0);
    }
  });

  test("domain RAG opens Evidence Panel with safe rows", async ({ page }) => {
    const seed = readSeedInfo();
    await loginAsAdmin(page);
    await page.getByLabel("Knowledge Domain").selectOption({ label: seed.displayName });
    await sendChatMessage(page, E2E_DOMAIN_QUESTION);

    await waitForStreamSettled(page);

    const evidence = page.getByRole("complementary", { name: "Evidence" });
    await expect(evidence).toBeVisible({ timeout: 120_000 });
    const rows = evidence.getByRole("listitem");
    await expect(rows.first()).toBeVisible({ timeout: 60_000 });
    expect(await rows.count()).toBeGreaterThanOrEqual(1);

    const rowText = await rows.first().innerText();
    expect(rowText.toLowerCase()).not.toMatch(/\b(password|bearer|api[_-]?key|token)\b/);
    // Seed fixture labels appear as safe Evidence DTO fields (sourceLabel / excerpt).
    expect(rowText).toMatch(/e2e-pilot|E2E Pilot|lockout|startup/i);
  });
});
