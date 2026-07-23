import { expect, test } from "@playwright/test";
import { loginAsAdmin, loginAsMember, logout } from "./helpers/auth";
import { readSeedInfo } from "./helpers/stack-seed";

test.describe.configure({ mode: "serial" });

test.describe("Phase 1 documents boundary", () => {
  test("admin source selection exposes deliberate governed-preview unavailability", async ({ page }) => {
    const seed = readSeedInfo();
    await loginAsAdmin(page);
    await page.goto("/documents");
    await expect(page.getByRole("heading", { name: "Source Documents" })).toBeVisible();
    await page.getByLabel("Knowledge Domain").selectOption({ label: seed.displayName });

    const firstSource = page.locator("[data-filename]").first();
    await expect(firstSource).toBeVisible({ timeout: 60_000 });
    await firstSource.click();
    await expect(page.getByText(/Governed document preview is not available/)).toBeVisible();
    await expect(page.getByTestId("documents-pdf-preview")).toHaveCount(0);
    await expect(page.getByTestId("documents-text-preview")).toHaveCount(0);
    await logout(page);
  });

  test("member document library remains explicitly unavailable", async ({ page }) => {
    await loginAsMember(page);
    await page.goto("/documents");
    await expect(page.getByText(/governed member document library is not available/i)).toBeVisible();
    await expect(page.getByTestId("documents-upload-button")).toHaveCount(0);
    await logout(page);
  });
});
