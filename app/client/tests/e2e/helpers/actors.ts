/** Fixture actors from docs/quality/seeded-demo-and-test-data.md (P12-07 U3). */

import type { Browser, BrowserContext, Page } from "@playwright/test";
import { expect } from "@playwright/test";
import { loadStackEnv, requireAdminCredentials } from "./env";
import {
  E2E_MEMBER_PASSWORD,
  E2E_MEMBER_USERNAME,
  ensureE2EMemberUser,
  ensureNamedActorUser,
} from "./stack-seed";
import { assertNoAuthTokensInBrowserStorage, expectChatShellReady } from "./storage";

export type ActorId = "ava" | "mina" | "noah";

export type ActorCredentials = {
  id: ActorId;
  username: string;
  password: string;
  role: "administrator" | "member";
};

export const NOAH_USERNAME = "e2e-noah@example.test";
export const NOAH_PASSWORD = "e2e-noah-password";

export function resolveActor(id: ActorId): ActorCredentials {
  const env = loadStackEnv();
  if (id === "ava") {
    const { username, password } = requireAdminCredentials(env);
    return { id, username, password, role: "administrator" };
  }
  if (id === "mina") {
    return {
      id,
      username: env.CE_E2E_MEMBER_USERNAME || E2E_MEMBER_USERNAME,
      password: env.CE_E2E_MEMBER_PASSWORD || E2E_MEMBER_PASSWORD,
      role: "member",
    };
  }
  return {
    id,
    username: env.CE_E2E_NOAH_USERNAME || NOAH_USERNAME,
    password: env.CE_E2E_NOAH_PASSWORD || NOAH_PASSWORD,
    role: "member",
  };
}

export function ensureFixtureActors() {
  ensureE2EMemberUser();
  const noah = resolveActor("noah");
  ensureNamedActorUser(noah.username, noah.password, "member");
}

export async function loginAsActor(page: Page, id: ActorId) {
  const actor = resolveActor(id);
  await page.goto("/login");
  await page.locator("#username").fill(actor.username);
  await page.locator("#password").fill(actor.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expectChatShellReady(page);
  await assertNoAuthTokensInBrowserStorage(page);
}

export async function newActorContext(
  browser: Browser,
  id: ActorId,
): Promise<{ context: BrowserContext; page: Page; actor: ActorCredentials }> {
  const actor = resolveActor(id);
  const context = await browser.newContext();
  const page = await context.newPage();
  await loginAsActor(page, id);
  return { context, page, actor };
}

export async function expectLoginDeniedNondisclosing(page: Page) {
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByText(/sign in failed|invalid|credentials/i)).toBeVisible();
  const body = await page.locator("body").innerText();
  expect(body.toLowerCase()).not.toMatch(/\b(stack|sql|traceback|password hash|argon)\b/);
}
