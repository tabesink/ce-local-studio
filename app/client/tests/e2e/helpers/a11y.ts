import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

/** Critical/serious axe violations must be empty on golden routes. */
export async function expectNoCriticalAxeViolations(page: Page, label: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const serious = results.violations.filter(
    (v) => v.impact === "critical" || v.impact === "serious",
  );
  expect(serious, `${label}: ${JSON.stringify(serious, null, 2)}`).toEqual([]);
}
