import { defaultAppearance, THEME_TOKEN_KEYS } from "./appearanceTypes.ts";
import { fontFamilies, themeCatalog } from "./themeCatalog.ts";

/**
 * Blocking pre-paint bootstrap for root layout.
 * Embeds catalog + apply math so FOUC is avoided without importing React.
 * Reads ce.appearance first; migrates legacy ce.theme / ce.density on miss.
 */
export function getAppearanceBootstrapScript(): string {
  const payload = JSON.stringify({
    defaults: defaultAppearance,
    catalog: themeCatalog.map((theme) => ({ id: theme.id, tokens: theme.tokens })),
    fonts: fontFamilies.map((font) => ({ id: font.id, stack: font.stack })),
    tokenKeys: THEME_TOKEN_KEYS,
  });

  return `(() => {
  try {
    var P = ${payload};
    var store = window.localStorage;
    function isThemeId(id) {
      for (var i = 0; i < P.catalog.length; i++) if (P.catalog[i].id === id) return true;
      return false;
    }
    function isDensity(id) { return id === "compact" || id === "comfortable"; }
    function normalize(raw) {
      var prefs = Object.assign({}, P.defaults, raw || {});
      prefs.tokenOverrides = Object.assign({}, (raw && raw.tokenOverrides) || {});
      if (!isThemeId(prefs.themeId)) prefs.themeId = P.defaults.themeId;
      if (prefs.themeMode !== "light" && prefs.themeMode !== "dark" && prefs.themeMode !== "system") {
        prefs.themeMode = prefs.themeId === "zai-light" ? "light" : "dark";
      }
      if (!isDensity(prefs.density)) prefs.density = P.defaults.density;
      if (typeof prefs.fontFamilyId !== "string" || !prefs.fontFamilyId) prefs.fontFamilyId = P.defaults.fontFamilyId;
      if (typeof prefs.fontSize !== "number" || !isFinite(prefs.fontSize)) prefs.fontSize = P.defaults.fontSize;
      if (typeof prefs.uiScale !== "number" || !isFinite(prefs.uiScale)) prefs.uiScale = P.defaults.uiScale;
      if (typeof prefs.radiusBase !== "number" || !isFinite(prefs.radiusBase)) prefs.radiusBase = P.defaults.radiusBase;
      return prefs;
    }
    function read() {
      var raw = store.getItem("ce.appearance");
      if (raw) {
        try { return normalize(JSON.parse(raw)); } catch (e) {}
      }
      var legacyTheme = store.getItem("ce.theme");
      var legacyDensity = store.getItem("ce.density");
      var themeId = isThemeId(legacyTheme) ? legacyTheme : P.defaults.themeId;
      var density = isDensity(legacyDensity) ? legacyDensity : P.defaults.density;
      var migrated = normalize({
        themeId: themeId,
        themeMode: themeId === "zai-light" ? "light" : "dark",
        density: density
      });
      try {
        store.setItem("ce.appearance", JSON.stringify(migrated));
        store.setItem("ce.theme", themeId === "zai-light" ? "zai-light" : "zai-dark");
        store.setItem("ce.density", migrated.density);
      } catch (e) {}
      return migrated;
    }
    function tokensFor(prefs) {
      var base = P.catalog[0].tokens;
      for (var i = 0; i < P.catalog.length; i++) {
        if (P.catalog[i].id === prefs.themeId) { base = P.catalog[i].tokens; break; }
      }
      return Object.assign({}, base, prefs.tokenOverrides || {});
    }
    function apply(prefs) {
      var root = document.documentElement;
      var binary = prefs.themeId === "zai-light" ? "zai-light" : "zai-dark";
      var factor = prefs.density === "comfortable" ? 1.05 : 1;
      var scale = Number((factor * prefs.uiScale).toFixed(4));
      var tokens = tokensFor(prefs);
      root.dataset.theme = binary;
      root.dataset.density = prefs.density;
      root.style.setProperty("--ui-scale", String(scale));
      root.style.setProperty("--radius-base", prefs.radiusBase + "px");
      root.style.setProperty("--app-font-size", prefs.fontSize + "px");
      for (var f = 0; f < P.fonts.length; f++) {
        if (P.fonts[f].id === prefs.fontFamilyId) {
          root.style.setProperty("--font-geist-sans", P.fonts[f].stack);
          break;
        }
      }
      for (var k = 0; k < P.tokenKeys.length; k++) {
        var key = P.tokenKeys[k];
        if (tokens[key]) root.style.setProperty("--" + key, tokens[key]);
      }
      if (tokens.accent) root.style.setProperty("--color-brand", tokens.accent);
    }
    apply(read());
  } catch (e) {}
})();`;
}
