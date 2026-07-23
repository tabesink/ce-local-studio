"use client";

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import {
  applyAppearance,
  applyThemeId,
  applyThemeMode,
  defaultAppearance,
  patchAppearance,
  patchToken,
  readAppearance,
  resetTokens,
  resolveTokens,
  writeAppearance,
  type AppearancePreferences,
  type DensityId,
  type ThemeId,
  type ThemeMode,
  type ThemeTokens,
} from "./appearanceRuntime.ts";
import { fontFamilies, themeCatalog } from "./themeCatalog.ts";
import type { ThemeMeta } from "./appearanceTypes.ts";

type AppearanceContextValue = {
  preferences: AppearancePreferences;
  hydrated: boolean;
  themes: ThemeMeta[];
  fontFamilies: typeof fontFamilies;
  activeTheme: ThemeMeta;
  tokens: ThemeTokens;
  setThemeMode: (mode: ThemeMode) => void;
  setThemeId: (themeId: ThemeId) => void;
  setDensity: (density: DensityId) => void;
  patchPreference: (patch: Partial<AppearancePreferences>) => void;
  patchToken: (key: keyof ThemeTokens, value: string) => void;
  resetTokens: () => void;
};

const AppearanceContext = createContext<AppearanceContextValue | null>(null);

function commit(prefs: AppearancePreferences) {
  writeAppearance(prefs);
  if (typeof document !== "undefined") {
    applyAppearance(document.documentElement, prefs);
  }
}

export function AppearanceProvider({ children }: { children: ReactNode }) {
  const [preferences, setPreferences] = useState<AppearancePreferences>(defaultAppearance);
  const [hydrated, setHydrated] = useState(false);
  const preferencesRef = useRef(preferences);
  preferencesRef.current = preferences;

  useEffect(() => {
    const next = readAppearance();
    preferencesRef.current = next;
    setPreferences(next);
    applyAppearance(document.documentElement, next);
    setHydrated(true);
  }, []);

  function update(recipe: (current: AppearancePreferences) => AppearancePreferences) {
    const next = recipe(preferencesRef.current);
    preferencesRef.current = next;
    commit(next);
    setPreferences(next);
  }

  const activeTheme = themeCatalog.find((theme) => theme.id === preferences.themeId) ?? themeCatalog[0];
  const tokens = resolveTokens(preferences);

  const value: AppearanceContextValue = {
    preferences,
    hydrated,
    themes: themeCatalog,
    fontFamilies,
    activeTheme,
    tokens,
    setThemeMode: (themeMode) => update((current) => applyThemeMode(current, themeMode)),
    setThemeId: (themeId) => update((current) => applyThemeId(current, themeId)),
    setDensity: (density) => update((current) => patchAppearance(current, { density })),
    patchPreference: (patch) => update((current) => patchAppearance(current, patch)),
    patchToken: (key, value) => update((current) => patchToken(current, key, value)),
    resetTokens: () => update((current) => resetTokens(current)),
  };

  return <AppearanceContext.Provider value={value}>{children}</AppearanceContext.Provider>;
}

export function useAppearance(): AppearanceContextValue {
  const ctx = useContext(AppearanceContext);
  if (!ctx) {
    throw new Error("useAppearance must be used within AppearanceProvider");
  }
  return ctx;
}
