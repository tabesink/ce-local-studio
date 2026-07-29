import { expect, test } from "@playwright/test";
import { loginAsActor, newActorContext } from "./helpers/actors";
import { readSeedInfo } from "./helpers/stack-seed";

/**
 * E2E-M11 browser half: open document surface while admin deletes a cited/preview source.
 * API redaction altitude is credited to P12-03; this proves open-panel UX safety.
 */
test.describe("E2E-M11 open panel during source delete @pr-fast", () => {
  test("member open documents + admin delete keeps safe recovery @pr-fast", async ({ browser }) => {
    const seed = readSeedInfo();
    const sourceId = seed.pdfSourceId || seed.markdownSourceId;
    if (!sourceId) {
      test.skip(true, "No seeded source ids for delete probe");
      return;
    }

    const member = await newActorContext(browser, "mina");
    const admin = await newActorContext(browser, "ava");
    try {
      await member.page.goto("/documents");
      await expect(member.page.getByRole("heading", { name: "Source Documents" })).toBeVisible({
        timeout: 60_000,
      });

      const csrf =
        (await admin.page.context().cookies()).find((cookie) => cookie.name === "ce_csrf")?.value ??
        "";
      const listed = await admin.page.request.get(
        `/api/v1/admin/domains/${encodeURIComponent(seed.domainId)}/sources`,
      );
      const listedBody = (await listed.json().catch(() => null)) as {
        sources?: Array<{ id?: string; version?: number }>;
      } | null;
      const row = listedBody?.sources?.find((source) => source.id === sourceId);
      const version = row?.version;
      const headers: Record<string, string> = {};
      if (csrf) headers["X-CSRF-Token"] = csrf;
      if (typeof version === "number") headers["If-Match"] = String(version);

      const del = await admin.page.request.delete(
        `/api/v1/admin/domains/${encodeURIComponent(seed.domainId)}/sources/${encodeURIComponent(sourceId)}`,
        { headers },
      );
      // Accept success, conflict, or precondition — UI must not crash afterward.
      expect([200, 202, 204, 409, 412, 404, 422]).toContain(del.status());

      await member.page.reload();
      const body = await member.page.locator("body").innerText();
      const lower = body.toLowerCase();
      expect(lower).not.toContain("traceback");
      expect(lower).not.toContain("working_dir");
      expect(lower).not.toContain("object key");
      await expect(member.page.getByRole("heading", { name: "Source Documents" })).toBeVisible({
        timeout: 60_000,
      });
    } finally {
      await member.context.close();
      await admin.context.close();
    }
  });

  test("admin domains source lifecycle chrome remains operable @pr-fast", async ({ page }) => {
    await loginAsActor(page, "ava");
    await page.goto("/settings?section=domains");
    await expect(page.getByText("Knowledge Domains")).toBeVisible();
  });
});