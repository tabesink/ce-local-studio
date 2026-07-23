import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { loginAsAdmin, sendChatMessage } from "./helpers/auth";
import {
  E2E_DOMAIN_QUESTION,
  readSeedInfo,
} from "./helpers/stack-seed";

const ARTIFACTS = path.resolve(__dirname, "artifacts");

type Theme = "zai-dark" | "zai-light";

const LOGIN_SHOTS: Array<{ name: string; width: number; height: number; theme: Theme }> = [
  { name: "login-1440x900-dark", width: 1440, height: 900, theme: "zai-dark" },
  { name: "login-1440x900-light", width: 1440, height: 900, theme: "zai-light" },
  { name: "login-1280x800-dark", width: 1280, height: 800, theme: "zai-dark" },
  { name: "login-390x844-dark", width: 390, height: 844, theme: "zai-dark" },
];

const CHAT_SHOTS: Array<{ name: string; width: number; height: number; theme: Theme }> = [
  { name: "chat-1440x900-dark", width: 1440, height: 900, theme: "zai-dark" },
  { name: "chat-1440x900-light", width: 1440, height: 900, theme: "zai-light" },
  { name: "chat-1280x800-dark", width: 1280, height: 800, theme: "zai-dark" },
  { name: "chat-390x844-dark", width: 390, height: 844, theme: "zai-dark" },
];

async function applyTheme(page: import("@playwright/test").Page, theme: Theme) {
  await page.evaluate((next) => {
    const prefs = {
      themeMode: next === "zai-light" ? "light" : "dark",
      themeId: next,
      density: "compact",
      fontFamilyId: "geist",
      fontSize: 13,
      uiScale: 1,
      radiusBase: 7,
      tokenOverrides: {},
    };
    window.localStorage.setItem("ce.appearance", JSON.stringify(prefs));
    window.localStorage.setItem("ce.theme", next);
    window.localStorage.setItem("ce.density", "compact");
    document.documentElement.dataset.theme = next;
    document.documentElement.dataset.density = "compact";
  }, theme);
}

test.describe.configure({ mode: "serial" });

test("DESIGN screenshot matrix for login and chat", async ({ browser, page }) => {
  test.setTimeout(300_000);
  fs.mkdirSync(ARTIFACTS, { recursive: true });

  // Login shots must use an unauthenticated context — AppLayout redirects
  // authenticated sessions from /login to /chat.
  const loginContext = await browser.newContext();
  const loginPage = await loginContext.newPage();
  for (const shot of LOGIN_SHOTS) {
    await loginPage.setViewportSize({ width: shot.width, height: shot.height });
    await loginPage.goto("/login");
    await expect(loginPage.locator("#username")).toBeVisible();
    await expect(loginPage.getByRole("button", { name: "Sign in" })).toBeVisible();
    await applyTheme(loginPage, shot.theme);
    const filePath = path.join(ARTIFACTS, `${shot.name}.png`);
    await loginPage.screenshot({ path: filePath, fullPage: false });
    expect(fs.existsSync(filePath)).toBeTruthy();
  }
  await loginContext.close();

  const seed = readSeedInfo();
  await page.setViewportSize({ width: 1440, height: 900 });
  await loginAsAdmin(page);
  await page.getByLabel("Knowledge Domain").selectOption({ label: seed.displayName });
  await sendChatMessage(page, E2E_DOMAIN_QUESTION);

  const evidence = page.getByRole("complementary", { name: "Evidence" });
  await expect(evidence).toBeVisible({ timeout: 120_000 });
  await expect(evidence.getByRole("listitem").first()).toBeVisible({ timeout: 60_000 });

  // Stay on the live chat surface — do not reload /chat (that clears the turn).
  for (const shot of CHAT_SHOTS) {
    await page.setViewportSize({ width: shot.width, height: shot.height });
    await applyTheme(page, shot.theme);
    if (shot.width <= 400) {
      await expect(page.getByLabel("Open navigation menu")).toBeVisible();
      // Mobile uses a slide-over; desktop aside is lg:flex-only.
    } else {
      await expect(evidence).toBeVisible();
    }
    const filePath = path.join(ARTIFACTS, `${shot.name}.png`);
    await page.screenshot({ path: filePath, fullPage: false });
    expect(fs.existsSync(filePath)).toBeTruthy();
  }
});
