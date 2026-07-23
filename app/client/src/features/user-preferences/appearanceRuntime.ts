import {
  APPEARANCE_STORAGE_KEY,
  LEGACY_DENSITY_KEY,
  LEGACY_THEME_KEY,
  THEME_TOKEN_KEYS,
  defaultAppearance,
  type AppearancePreferences,
  type DensityId,
  type ThemeId,
  type ThemeMode,
  type ThemeTokens,
} from "./appearanceTypes.ts";
import { fontFamilies, themeCatalog } from "./themeCatalog.ts";
import { isAllowedUiStorageKey, readUiPreference, writeUiPreference } from "../../lib/storage.ts";
import type { UiStorageKey } from "../../lib/storage.ts";

export { defaultAppearance } from "./appearanceTypes.ts";
export type { AppearancePreferences, DensityId, ThemeId, ThemeMode, ThemeTokens };

export interface AppearanceStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem?(key: string): void;
}

export interface AppearanceRoot {
  dataset: DOMStringMap | Record<string, string | undefined>;
  style: {
    setProperty(name: string, value: string): void;
    removeProperty(name: string): void;
  };
}

const THEME_IDS = new Set<string>(themeCatalog.map((theme) => theme.id));
const DENSITY_IDS = new Set<string>(["compact", "comfortable"]);
const THEME_MODES = new Set<string>(["light", "dark", "system"]);

function browserStorage(): AppearanceStorage | null {
  if (typeof window === "undefined") return null;
  return {
    getItem(key: string) {
      if (!isAllowedUiStorageKey(key)) return null;
      return readUiPreference(key);
    },
    setItem(key: string, value: string) {
      if (!isAllowedUiStorageKey(key)) return;
      writeUiPreference(key as UiStorageKey, value);
    },
  };
}

function isThemeId(value: unknown): value is ThemeId {
  return typeof value === "string" && THEME_IDS.has(value);
}

function isDensityId(value: unknown): value is DensityId {
  return typeof value === "string" && DENSITY_IDS.has(value);
}

function isThemeMode(value: unknown): value is ThemeMode {
  return typeof value === "string" && THEME_MODES.has(value);
}

export function binaryThemeId(themeId: ThemeId): "zai-dark" | "zai-light" {
  return themeId === "zai-light" ? "zai-light" : "zai-dark";
}

export function densityFactor(density: DensityId): number {
  return density === "comfortable" ? 1.05 : 1;
}

export function effectiveUiScale(density: DensityId, uiScale: number): number {
  /* Round to avoid IEEE noise (1.05 * 1.1 → 1.1550000000000002). */
  return Number((densityFactor(density) * uiScale).toFixed(4));
}

export function resolveTokens(prefs: AppearancePreferences): ThemeTokens {
  const theme = themeCatalog.find((entry) => entry.id === prefs.themeId) ?? themeCatalog[0];
  return { ...theme.tokens, ...prefs.tokenOverrides };
}

export function applyThemeMode(
  current: AppearancePreferences,
  themeMode: ThemeMode,
): AppearancePreferences {
  return {
    ...current,
    themeMode,
    themeId:
      themeMode === "light"
        ? "zai-light"
        : themeMode === "dark" && current.themeId === "zai-light"
          ? "zai-dark"
          : current.themeId,
  };
}

export function applyThemeId(current: AppearancePreferences, themeId: ThemeId): AppearancePreferences {
  return {
    ...current,
    themeId,
    themeMode: themeId === "zai-light" ? "light" : "dark",
    tokenOverrides: {},
  };
}

export function patchAppearance(
  current: AppearancePreferences,
  patch: Partial<AppearancePreferences>,
): AppearancePreferences {
  return { ...current, ...patch };
}

export function patchToken(
  current: AppearancePreferences,
  key: keyof ThemeTokens,
  value: string,
): AppearancePreferences {
  return {
    ...current,
    tokenOverrides: { ...current.tokenOverrides, [key]: value },
  };
}

export function resetTokens(current: AppearancePreferences): AppearancePreferences {
  return { ...current, tokenOverrides: {} };
}

export function normalizeAppearance(raw: Partial<AppearancePreferences> | null | undefined): AppearancePreferences {
  const merged: AppearancePreferences = {
    ...defaultAppearance,
    ...(raw ?? {}),
    tokenOverrides: { ...(raw?.tokenOverrides ?? {}) },
  };

  if (!isThemeId(merged.themeId)) merged.themeId = defaultAppearance.themeId;
  if (!isThemeMode(merged.themeMode)) {
    merged.themeMode = merged.themeId === "zai-light" ? "light" : "dark";
  }
  if (!isDensityId(merged.density)) merged.density = defaultAppearance.density;
  if (!fontFamilies.some((font) => font.id === merged.fontFamilyId)) {
    merged.fontFamilyId = defaultAppearance.fontFamilyId;
  }
  if (typeof merged.fontSize !== "number" || !Number.isFinite(merged.fontSize)) {
    merged.fontSize = defaultAppearance.fontSize;
  } else {
    merged.fontSize = Math.min(20, Math.max(13, Math.round(merged.fontSize)));
  }
  if (typeof merged.uiScale !== "number" || !Number.isFinite(merged.uiScale)) {
    merged.uiScale = defaultAppearance.uiScale;
  } else {
    merged.uiScale = Math.min(1.25, Math.max(0.85, Number(merged.uiScale.toFixed(2))));
  }
  if (typeof merged.radiusBase !== "number" || !Number.isFinite(merged.radiusBase)) {
    merged.radiusBase = defaultAppearance.radiusBase;
  } else {
    merged.radiusBase = Math.min(14, Math.max(0, Math.round(merged.radiusBase)));
  }
  if (!merged.tokenOverrides || typeof merged.tokenOverrides !== "object") {
    merged.tokenOverrides = {};
  }

  return merged;
}

export function migrateFromLegacy(
  legacyTheme: string | null,
  legacyDensity: string | null,
): AppearancePreferences {
  const themeId = isThemeId(legacyTheme) ? legacyTheme : defaultAppearance.themeId;
  const density = isDensityId(legacyDensity) ? legacyDensity : defaultAppearance.density;
  return normalizeAppearance({
    ...defaultAppearance,
    themeId,
    themeMode: themeId === "zai-light" ? "light" : "dark",
    density,
  });
}

export function readAppearance(storage: AppearanceStorage | null = browserStorage()): AppearancePreferences {
  if (!storage) return { ...defaultAppearance, tokenOverrides: {} };

  const raw = storage.getItem(APPEARANCE_STORAGE_KEY);
  if (raw) {
    try {
      return normalizeAppearance(JSON.parse(raw) as Partial<AppearancePreferences>);
    } catch {
      // fall through to legacy migration
    }
  }

  const migrated = migrateFromLegacy(
    storage.getItem(LEGACY_THEME_KEY),
    storage.getItem(LEGACY_DENSITY_KEY),
  );
  writeAppearance(migrated, storage);
  return migrated;
}

export function writeAppearance(
  prefs: AppearancePreferences,
  storage: AppearanceStorage | null = browserStorage(),
): void {
  if (!storage) return;
  const normalized = normalizeAppearance(prefs);
  try {
    storage.setItem(APPEARANCE_STORAGE_KEY, JSON.stringify(normalized));
    storage.setItem(LEGACY_THEME_KEY, binaryThemeId(normalized.themeId));
    storage.setItem(LEGACY_DENSITY_KEY, normalized.density);
  } catch {
    // local-only preference; storage failures are non-fatal
  }
}

export function applyAppearance(root: AppearanceRoot, prefs: AppearancePreferences): void {
  const normalized = normalizeAppearance(prefs);
  const tokens = resolveTokens(normalized);
  const binary = binaryThemeId(normalized.themeId);

  root.dataset.theme = binary;
  root.dataset.density = normalized.density;

  root.style.setProperty("--ui-scale", String(effectiveUiScale(normalized.density, normalized.uiScale)));
  root.style.setProperty("--radius-base", `${normalized.radiusBase}px`);
  root.style.setProperty("--app-font-size", `${normalized.fontSize}px`);

  const font = fontFamilies.find((family) => family.id === normalized.fontFamilyId);
  if (font) root.style.setProperty("--font-geist-sans", font.stack);

  for (const key of THEME_TOKEN_KEYS) {
    const value = tokens[key];
    if (value) root.style.setProperty(`--${key}`, value);
  }

  /* Brand alias so --color-brand consumers pick up accent themes. */
  root.style.setProperty("--color-brand", tokens.accent);
}
