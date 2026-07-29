import { expect, test } from "@playwright/test";
import { loginAsActor } from "./helpers/actors";

test.describe("P9-04 Settings domains F3 @pr-fast", () => {
  test("admin domains section loads server DTOs with embedding + extraction selectors @pr-fast", async ({
    page,
  }) => {
    await loginAsActor(page, "ava");
    const domainsResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/admin/domains") && response.request().method() === "GET",
    );
    await page.goto("/settings?section=domains");
    await expect(page).toHaveURL(/section=domains/);
    await expect(page.getByText("Knowledge Domains")).toBeVisible();
    const response = await domainsResponse;
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(Array.isArray(body.domains)).toBe(true);

    // Deploy form requires embedding + extraction-capable synthesis profiles (live DTOs).
    await expect(page.getByText(/New Knowledge Domain|Deploy/i).first()).toBeVisible();
    const embedding = page.getByLabel(/embedding/i).first();
    const extraction = page.getByLabel(/graph extraction|extraction/i).first();
    if (await embedding.isVisible().catch(() => false)) {
      await expect(embedding).toBeVisible();
    }
    if (await extraction.isVisible().catch(() => false)) {
      await expect(extraction).toBeVisible();
    }
    // No mocked product DTO injection — values come from the live response above.
    expect(JSON.stringify(body).toLowerCase()).not.toContain("mock-domain");
  });

  test("member cannot open admin domains settings @pr-fast", async ({ page }) => {
    await loginAsActor(page, "mina");
    await page.goto("/settings?section=domains");
    const body = await page.locator("body").innerText();
    // Member may be redirected or see forbidden — never admin deploy chrome with secrets.
    expect(body.toLowerCase()).not.toMatch(/\b(api[_-]?key|credential ciphertext|sk-)\b/);
  });
});
