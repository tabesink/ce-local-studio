import { expect, test } from "@playwright/test";
import { newActorContext } from "./helpers/actors";
import { sendChatMessage } from "./helpers/auth";
import { E2E_DOMAIN_QUESTION, readSeedInfo } from "./helpers/stack-seed";

const RELEASE_GATE =
  process.env.CE_P12_07_RELEASE === "1" ||
  process.env.CE_P12_07_RELEASE?.toLowerCase() === "true";

test.describe("E2E-C01 / AE5 concurrent isolation + capacity @release", () => {
  test.skip(!RELEASE_GATE, "Set CE_P12_07_RELEASE=1 for the @release lane");

  test("Mina and Noah concurrent domain chats stay isolated @release", async ({ browser }) => {
    const seed = readSeedInfo();
    const mina = await newActorContext(browser, "mina");
    const noah = await newActorContext(browser, "noah");
    try {
      await mina.page.getByLabel("Knowledge Domain").selectOption({ label: seed.displayName });
      await noah.page.getByLabel("Knowledge Domain").selectOption({ label: seed.displayName });

      await Promise.all([
        sendChatMessage(mina.page, `${E2E_DOMAIN_QUESTION} (mina)`),
        sendChatMessage(noah.page, `${E2E_DOMAIN_QUESTION} (noah)`),
      ]);

      await expect(mina.page.getByTestId("chat-streaming")).toHaveAttribute("data-streaming", "false", {
        timeout: 180_000,
      });
      await expect(noah.page.getByTestId("chat-streaming")).toHaveAttribute("data-streaming", "false", {
        timeout: 180_000,
      });

      const minaText = await mina.page.locator("body").innerText();
      const noahText = await noah.page.locator("body").innerText();
      expect(minaText).toContain("(mina)");
      expect(noahText).toContain("(noah)");
      expect(minaText).not.toContain("(noah)");
      expect(noahText).not.toContain("(mina)");
    } finally {
      await mina.context.close();
      await noah.context.close();
    }
  });

  test("graph workbench loads for two members without cross-leak of private bags @release", async ({
    browser,
  }) => {
    const seed = readSeedInfo();
    const mina = await newActorContext(browser, "mina");
    const noah = await newActorContext(browser, "noah");
    try {
      await Promise.all([
        mina.page.goto(`/database-visualize?domain=${encodeURIComponent(seed.domainId)}`),
        noah.page.goto(`/database-visualize?domain=${encodeURIComponent(seed.domainId)}`),
      ]);
      await expect(mina.page.getByTestId("graph-workbench")).toBeVisible();
      await expect(noah.page.getByTestId("graph-workbench")).toBeVisible();
      for (const page of [mina.page, noah.page]) {
        const body = await page.locator("body").innerText();
        expect(body.toLowerCase()).not.toMatch(/working_dir|chunk_id|traceback|bearer/);
      }
    } finally {
      await mina.context.close();
      await noah.context.close();
    }
  });
});

test.describe("AE8 / AE10 release demo path @release", () => {
  test.skip(!RELEASE_GATE, "Set CE_P12_07_RELEASE=1 for the @release lane");

  test("seeded domain graph then grounded figure question path @release", async ({ browser }) => {
    const seed = readSeedInfo();
    const mina = await newActorContext(browser, "mina");
    try {
      await mina.page.goto(`/database-visualize?domain=${encodeURIComponent(seed.domainId)}`);
      await expect(mina.page.getByTestId("graph-workbench")).toBeVisible();
      // Deterministic adapters may surface Pump/Relief valve after pump fixture index.
      const summary = await mina.page.getByTestId("graph-accessible-summary").innerText();
      expect(summary.toLowerCase()).not.toContain("working_dir");

      await mina.page.goto("/chat");
      await mina.page.getByLabel("Knowledge Domain").selectOption({ label: seed.displayName });
      await sendChatMessage(mina.page, "Where is the relief valve?");
      await expect(mina.page.getByTestId("chat-streaming")).toHaveAttribute("data-streaming", "false", {
        timeout: 180_000,
      });
      const assistant = mina.page.getByTestId("assistant-turn").last();
      await expect(assistant).toBeVisible();
      const answer = await assistant.innerText();
      // Live prose may vary; require grounded citation marker and pump/relief fact family.
      expect(answer).toMatch(/\[1\]/);
      expect(answer.toLowerCase()).toMatch(/relief|pump|downstream/);
    } finally {
      await mina.context.close();
    }
  });
});

test.describe("R9 non-PDF preview failure surface @release", () => {
  test.skip(!RELEASE_GATE, "Set CE_P12_07_RELEASE=1 for the @release lane");

  test("documents library remains safe without private renderer paths @release", async ({ page }) => {
    const { loginAsActor } = await import("./helpers/actors");
    await loginAsActor(page, "ava");
    await page.goto("/documents");
    await expect(page.getByRole("heading", { name: "Source Documents" })).toBeVisible();
    const body = await page.locator("body").innerText();
    expect(body.toLowerCase()).not.toContain("working_dir");
    expect(body.toLowerCase()).not.toContain("libreoffice");
  });
});
