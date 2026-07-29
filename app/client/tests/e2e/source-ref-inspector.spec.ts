import { expect, test } from "@playwright/test";
import { loginAsAdmin, logout, sendChatMessage } from "./helpers/auth";
import { E2E_DOMAIN_QUESTION, readSeedInfo } from "./helpers/stack-seed";

test.describe.configure({ mode: "serial" });

test.describe("Phase 1 evidence document-navigation boundary @pr-fast", () => {
  test("Evidence inspector enables Open in Library with opaque deep links @pr-fast", async ({ page }) => {
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
    await expect(page.getByTestId("inspector-tab-evidence")).toBeVisible();
    await expect(page.getByTestId("inspector-tab-refs")).toBeVisible();
    await expect(page.getByTestId("inspector-tab-source")).toBeVisible();

    const firstEvidence = evidence.getByRole("listitem").first();
    await expect(firstEvidence).toBeVisible({ timeout: 60_000 });
    await firstEvidence.click();

    await expect(evidence.getByTestId("evidence-selected-detail")).toBeVisible();

    await page.getByTestId("inspector-tab-source").click();
    const openInLibrary = page.getByTestId("open-in-library");
    await expect(openInLibrary).toBeEnabled();
    await openInLibrary.click();
    await expect(page).toHaveURL(/\/documents\?.*document=.+&evidence=/);
    await logout(page);
  });
});
