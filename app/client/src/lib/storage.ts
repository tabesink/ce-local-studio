export const UI_STORAGE_KEYS = [
  "ce.appearance",
  "ce.theme",
  "ce.density",
  "ce.railCollapsed",
  "ce.panelWidths",
  "ce.lastRouteGroup",
] as const;

export type UiStorageKey = (typeof UI_STORAGE_KEYS)[number];

const keySet = new Set<string>(UI_STORAGE_KEYS);

export function isAllowedUiStorageKey(key: string): key is UiStorageKey {
  return keySet.has(key);
}

export function readUiPreference(key: UiStorageKey): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(key);
}

export function writeUiPreference(key: UiStorageKey, value: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, value);
}

export function removeUiPreference(key: UiStorageKey) {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(key);
}
