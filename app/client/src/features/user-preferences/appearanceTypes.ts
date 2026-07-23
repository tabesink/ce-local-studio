export type ThemeMode = "light" | "dark" | "system";

export type ThemeId =
  | "zai-light"
  | "zai-dark"
  | "zai-sky"
  | "zai-violet"
  | "zai-emerald"
  | "zai-rose";

export type DensityId = "compact" | "comfortable";

export interface ThemeTokens {
  bg: string;
  fg: string;
  dim: string;
  border: string;
  surface: string;
  accent: string;
  hl1: string;
  hl2: string;
  hl3: string;
  err: string;
}

export type ThemeTokenKey = keyof ThemeTokens;

export interface ThemeMeta {
  id: ThemeId;
  name: string;
  description: string;
  group: string;
  swatches: [string, string, string, string];
  tokens: ThemeTokens;
}

export interface AppearancePreferences {
  themeMode: ThemeMode;
  themeId: ThemeId;
  density: DensityId;
  fontFamilyId: string;
  fontSize: number;
  uiScale: number;
  radiusBase: number;
  tokenOverrides: Partial<ThemeTokens>;
}

export const APPEARANCE_STORAGE_KEY = "ce.appearance";
export const LEGACY_THEME_KEY = "ce.theme";
export const LEGACY_DENSITY_KEY = "ce.density";

export const THEME_TOKEN_KEYS: ThemeTokenKey[] = [
  "bg",
  "fg",
  "dim",
  "border",
  "surface",
  "accent",
  "hl1",
  "hl2",
  "hl3",
  "err",
];

export const defaultAppearance: AppearancePreferences = {
  themeMode: "dark",
  themeId: "zai-dark",
  density: "compact",
  fontFamilyId: "geist",
  fontSize: 13,
  uiScale: 1,
  radiusBase: 7,
  tokenOverrides: {},
};
