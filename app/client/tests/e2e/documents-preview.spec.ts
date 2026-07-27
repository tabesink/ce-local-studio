import { expect, test } from "@playwright/test";
import { loginAsAdmin, loginAsMember, logout } from "./helpers/auth";
import { readSeedInfo } from "./helpers/stack-seed";

test.describe.configure({ mode: "serial" });

test.describe("Phase 1 documents library preview (P9-03)", () => {
  test("member library lists documents without admin mutating controls", async ({ page }) => {
    await loginAsMember(page);
    await page.goto("/documents");
    await expect(page.getByRole("heading", { name: "Source Documents" })).toBeVisible();
    await expect(page.getByTestId("documents-upload-button")).toHaveCount(0);
    await expect(page.getByTestId("documents-admin-actions")).toHaveCount(0);
    await expect(page.getByText(/governed member document library is not available/i)).toHaveCount(0);
    await logout(page);
  });

  test("admin can open a library row and see role-gated ops without inventing text preview", async ({
    page,
  }) => {
    const seed = readSeedInfo();
    await loginAsAdmin(page);
    await page.goto("/documents");
    await expect(page.getByRole("heading", { name: "Source Documents" })).toBeVisible();
    await page.getByLabel("Knowledge Domain").selectOption({ label: seed.displayName });

    const firstSource = page.locator("[data-filename]").first();
    await expect(firstSource).toBeVisible({ timeout: 60_000 });
    await firstSource.click();
    await expect(page.getByTestId("documents-preview-panel")).toBeVisible();
    await expect(page.getByTestId("documents-text-preview")).toHaveCount(0);

    const pdfPreview = page.getByTestId("documents-pdf-preview");
    const unavailable = page.getByTestId("documents-preview-unavailable");
    await expect(pdfPreview.or(unavailable)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("documents-admin-ops")).toBeVisible();
    await logout(page);
  });

  test("graph route stays unavailable with no domain selector", async ({ page }) => {
    await loginAsMember(page);
    await page.goto("/database-visualize");
    await expect(page.getByTestId("graph-unavailable")).toBeVisible();
    await expect(page.getByText(/Graph visualization is not available/i)).toBeVisible();
    await expect(page.getByLabel("Knowledge Domain")).toHaveCount(0);
    await logout(page);
  });
});
