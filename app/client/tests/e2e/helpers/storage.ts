import type { Page } from "@playwright/test";
import { expect } from "@playwright/test";
import { UI_STORAGE_KEYS } from "../../../src/lib/storage";

const ALLOWED = new Set<string>(UI_STORAGE_KEYS);
const FORBIDDEN_SUBSTR = ["token", "bearer", "password", "session"];

function assertSafeKeys(keys: string[], storageName: string) {
  for (const key of keys) {
    if (ALLOWED.has(key)) continue;
    const lower = key.toLowerCase();
    for (const needle of FORBIDDEN_SUBSTR) {
      if (lower.includes(needle)) {
        throw new Error(`${storageName} contains forbidden key: ${key}`);
      }
    }
  }
}

export async function assertNoAuthTokensInBrowserStorage(page: Page) {
  const snapshot = await page.evaluate(() => {
    const local: string[] = [];
    const session: string[] = [];
    for (let i = 0; i < window.localStorage.length; i += 1) {
      const key = window.localStorage.key(i);
      if (key) local.push(key);
    }
    for (let i = 0; i < window.sessionStorage.length; i += 1) {
      const key = window.sessionStorage.key(i);
      if (key) session.push(key);
    }
    return { local, session };
  });
  assertSafeKeys(snapshot.local, "localStorage");
  assertSafeKeys(snapshot.session, "sessionStorage");
}

export async function expectChatShellReady(page: Page) {
  await expect(page).toHaveURL(/\/chat/);
  await expect(page.getByLabel("Knowledge Domain")).toBeVisible();
}
