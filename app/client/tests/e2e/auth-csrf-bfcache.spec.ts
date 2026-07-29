import { expect, request, test } from "@playwright/test";
import { expectLoginDeniedNondisclosing, loginAsActor, resolveActor } from "./helpers/actors";
import { logout } from "./helpers/auth";
import { assertNoAuthTokensInBrowserStorage } from "./helpers/storage";

test.describe("E2E-M01 auth / CSRF / BFCache @pr-fast", () => {
  test("invalid login is nondisclosing @pr-fast", async ({ page }) => {
    await page.goto("/login");
    await page.locator("#username").fill("nobody@example.test");
    await page.locator("#password").fill("wrong-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expectLoginDeniedNondisclosing(page);
    await assertNoAuthTokensInBrowserStorage(page);
  });

  test("login rotates session and logout blocks Back cache @pr-fast", async ({ page }) => {
    await loginAsActor(page, "mina");
    await expect(page.getByLabel("Knowledge Domain")).toBeVisible();
    await logout(page);
    await page.goBack();
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByLabel("Knowledge Domain")).toHaveCount(0);
    await assertNoAuthTokensInBrowserStorage(page);
  });

  test("unsafe POST without CSRF is denied without secret leak @pr-fast", async ({ page }) => {
    await loginAsActor(page, "mina");
    const cookies = await page.context().cookies();
    const cookieHeader = cookies.map((cookie) => `${cookie.name}=${cookie.value}`).join("; ");
    const baseURL = page.url().origin;
    const api = await request.newContext({
      baseURL,
      extraHTTPHeaders: {
        Accept: "application/json",
        Cookie: cookieHeader,
        Origin: baseURL,
        // Intentionally omit X-CSRF-Token
      },
    });
    try {
      const response = await api.post("/api/v1/conversations", {
        data: { title: "csrf-probe" },
      });
      expect(response.status()).toBeGreaterThanOrEqual(400);
      const body = await response.json();
      expect(body?.error?.code).toBe("csrf_invalid");
      const text = JSON.stringify(body).toLowerCase();
      expect(text).not.toMatch(/\b(traceback|stack|secret|password|signing)\b/);
    } finally {
      await api.dispose();
    }
  });

  test("Ava admin login succeeds @pr-fast", async ({ page }) => {
    const ava = resolveActor("ava");
    expect(ava.role).toBe("administrator");
    await loginAsActor(page, "ava");
    await logout(page);
  });
});
