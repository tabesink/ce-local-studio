import type { Page } from "@playwright/test";

export type Theme = "zai-dark" | "zai-light";

/** Apply appearance tokens without persisting secrets or product content. */
export async function applyTheme(page: Page, theme: Theme) {
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

/** Freeze nondeterministic chrome for screenshot compare (caret, animations). */
export async function freezeForScreenshot(page: Page) {
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        caret-color: transparent !important;
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        transition-delay: 0s !important;
      }
    `,
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
}
