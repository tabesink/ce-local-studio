import type { ThemeMeta, ThemeTokens } from "./appearanceTypes.ts";
import { defaultAppearance } from "./appearanceTypes.ts";

/* Theme catalogue mirrored from LS user-preferences fixtures:
   Workbench Dark/Light plus four dark accent variants via withAccent. */

const ZAI_LIGHT: ThemeTokens = {
  bg: "#f4f5f5",
  fg: "#202123",
  dim: "#20212399",
  border: "#0d0d0d1a",
  surface: "#fbfbfb",
  accent: "#000000",
  hl1: "#6b8db5",
  hl2: "#2f8f5f",
  hl3: "#c8792f",
  err: "#e03131",
};

const ZAI_DARK: ThemeTokens = {
  bg: "#0f0f0f",
  fg: "#e7e7e7",
  dim: "#e7e7e799",
  border: "#ffffff14",
  surface: "#202020",
  accent: "#ffffff",
  hl1: "#7ea1c8",
  hl2: "#4aa06f",
  hl3: "#d48a4c",
  err: "#ff5c5c",
};

const withAccent = (base: ThemeTokens, accent: string): ThemeTokens => ({
  ...base,
  accent,
  hl1: accent,
});

const createTheme = (
  id: ThemeMeta["id"],
  name: string,
  description: string,
  group: string,
  tokens: ThemeTokens,
): ThemeMeta => ({
  id,
  name,
  description,
  group,
  swatches: [tokens.bg, tokens.surface, tokens.accent, tokens.fg],
  tokens,
});

export const themeCatalog: ThemeMeta[] = [
  createTheme(
    "zai-dark",
    "Workbench Dark",
    "Workbench — charcoal layers, quiet borders, muted data accents",
    "Workbench",
    ZAI_DARK,
  ),
  createTheme(
    "zai-light",
    "Workbench Light",
    "Workbench light — paper canvas, black brand, muted data accents",
    "Workbench",
    ZAI_LIGHT,
  ),
  createTheme("zai-sky", "Sky", "Workbench dark with a sky-blue brand accent", "Accents", withAccent(ZAI_DARK, "#4099ff")),
  createTheme(
    "zai-violet",
    "Violet",
    "Workbench dark with a violet brand accent",
    "Accents",
    withAccent(ZAI_DARK, "#7b5ce5"),
  ),
  createTheme(
    "zai-emerald",
    "Emerald",
    "Workbench dark with an emerald brand accent",
    "Accents",
    withAccent(ZAI_DARK, "#46bf72"),
  ),
  createTheme("zai-rose", "Rose", "Workbench dark with a rose brand accent", "Accents", withAccent(ZAI_DARK, "#ff5c5c")),
];

export const fontFamilies = [
  { id: "geist", label: "Geist", stack: `"Geist", ui-sans-serif, system-ui, sans-serif` },
  { id: "inter", label: "Inter", stack: `"Inter", ui-sans-serif, system-ui, sans-serif` },
  { id: "system", label: "System", stack: `ui-sans-serif, system-ui, sans-serif` },
] as const;

export { defaultAppearance };
