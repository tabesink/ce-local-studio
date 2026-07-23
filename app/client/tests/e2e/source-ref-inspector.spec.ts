import { expect, test } from "@playwright/test";
import { loginAsAdmin, logout, sendChatMessage } from "./helpers/auth";
import { E2E_DOMAIN_QUESTION, readSeedInfo } from "./helpers/stack-seed";

test.describe.configure({ mode: "serial" });

test.describe("Phase 1 evidence document-navigation boundary", () => {
  test("Evidence stays useful while document navigation is deliberately unavailable", async ({ page }) => {
    const seed = readSeedInfo();
    await loginAsAdmin(page);
    await page.getByLabel("Knowledge Domain").selectOption({ label: seed.displayName });
    await sendChatMessage(page, E2E_DOMAIN_QUESTION);

    const assistant = page.getByTestId("assistant-turn").last();
    await expect(assistant).toBeVisible({ timeout: 90_000 });
    await expect(page.getByTestId("chat-streaming")).toHaveAttribute("data-streaming", "false", {
      timeout: 90_000,
    });

    const evidence = page.getByRole("complementary", { name: "Evidence" });
    await expect(evidence).toBeVisible({ timeout: 120_000 });
    const firstEvidence = evidence.getByRole("listitem").first();
    await expect(firstEvidence).toBeVisible({ timeout: 60_000 });
    await firstEvidence.click();

    await expect(evidence.getByTestId("evidence-selected-detail")).toBeVisible();
    await expect(evidence.getByTestId("document-navigation-unavailable")).toContainText(
      "Document navigation is unavailable",
    );
    await expect(evidence.getByTestId("open-in-library")).toHaveCount(0);
    await expect(page).toHaveURL(/\/chat/);
    await logout(page);
  });
});
