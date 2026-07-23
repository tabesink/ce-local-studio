import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

async function loadRuntime() {
  const moduleUrl = pathToFileURL(join(root, "src/features/user-preferences/appearanceRuntime.ts")).href;
  return import(moduleUrl);
}

function createMemoryStorage(seed = {}) {
  const map = new Map(Object.entries(seed));
  return {
    getItem(key) {
      return map.has(key) ? map.get(key) : null;
    },
    setItem(key, value) {
      map.set(key, String(value));
    },
    removeItem(key) {
      map.delete(key);
    },
    _map: map,
  };
}

function createFakeRoot() {
  const props = new Map();
  return {
    dataset: {},
    style: {
      setProperty(name, value) {
        props.set(name, value);
      },
      removeProperty(name) {
        props.delete(name);
      },
      getPropertyValue(name) {
        return props.get(name) ?? "";
      },
    },
    _props: props,
  };
}

describe("appearance runtime helpers (F-009)", () => {
  it("defaults to Workbench Dark / compact / geist", async () => {
    const { defaultAppearance, readAppearance } = await loadRuntime();
    const storage = createMemoryStorage();
    const prefs = readAppearance(storage);

    assert.equal(prefs.themeId, "zai-dark");
    assert.equal(prefs.themeMode, "dark");
    assert.equal(prefs.density, "compact");
    assert.equal(prefs.fontFamilyId, "geist");
    assert.equal(prefs.fontSize, 13);
    assert.equal(prefs.uiScale, 1);
    assert.equal(prefs.radiusBase, 7);
    assert.deepEqual(prefs.tokenOverrides, {});
    assert.deepEqual(prefs, defaultAppearance);
  });

  it("migrates legacy ce.theme=zai-light into appearance", async () => {
    const { readAppearance } = await loadRuntime();
    const storage = createMemoryStorage({ "ce.theme": "zai-light" });
    const prefs = readAppearance(storage);

    assert.equal(prefs.themeId, "zai-light");
    assert.equal(prefs.themeMode, "light");
    assert.equal(prefs.density, "compact");
    assert.ok(storage.getItem("ce.appearance"));
  });

  it("Mode Light forces zai-light; Mode Dark from light → zai-dark; Mode Dark with sky keeps sky", async () => {
    const { applyThemeMode, defaultAppearance } = await loadRuntime();

    const light = applyThemeMode(defaultAppearance, "light");
    assert.equal(light.themeMode, "light");
    assert.equal(light.themeId, "zai-light");

    const darkFromLight = applyThemeMode(light, "dark");
    assert.equal(darkFromLight.themeMode, "dark");
    assert.equal(darkFromLight.themeId, "zai-dark");

    const withSky = { ...defaultAppearance, themeId: "zai-sky", themeMode: "dark" };
    const darkKeepsSky = applyThemeMode(withSky, "dark");
    assert.equal(darkKeepsSky.themeId, "zai-sky");

    const system = applyThemeMode(withSky, "system");
    assert.equal(system.themeMode, "system");
    assert.equal(system.themeId, "zai-sky");
  });

  it("setThemeId clears tokenOverrides and couples Mode for light/dark", async () => {
    const { applyThemeId, defaultAppearance } = await loadRuntime();
    const dirty = {
      ...defaultAppearance,
      tokenOverrides: { accent: "#ff0000" },
      themeMode: "dark",
      themeId: "zai-dark",
    };

    const sky = applyThemeId(dirty, "zai-sky");
    assert.equal(sky.themeId, "zai-sky");
    assert.equal(sky.themeMode, "dark");
    assert.deepEqual(sky.tokenOverrides, {});

    const light = applyThemeId(dirty, "zai-light");
    assert.equal(light.themeId, "zai-light");
    assert.equal(light.themeMode, "light");
    assert.deepEqual(light.tokenOverrides, {});
  });

  it("composes --ui-scale as densityFactor × uiScale", async () => {
    const { effectiveUiScale } = await loadRuntime();
    assert.equal(effectiveUiScale("compact", 1.1), 1.1);
    assert.equal(effectiveUiScale("comfortable", 1.1), 1.155);
    assert.equal(effectiveUiScale("compact", 1), 1);
    assert.equal(effectiveUiScale("comfortable", 1), 1.05);
  });

  it("applyAppearance sets binary data-theme only and writes composed scale", async () => {
    const { applyAppearance, defaultAppearance } = await loadRuntime();
    const root = createFakeRoot();

    applyAppearance(root, { ...defaultAppearance, themeId: "zai-sky", uiScale: 1.1, density: "comfortable" });
    assert.equal(root.dataset.theme, "zai-dark");
    assert.equal(root.dataset.density, "comfortable");
    assert.equal(root.style.getPropertyValue("--ui-scale"), "1.155");
    assert.equal(root.style.getPropertyValue("--accent"), "#4099ff");

    applyAppearance(root, { ...defaultAppearance, themeId: "zai-light" });
    assert.equal(root.dataset.theme, "zai-light");
  });

  it("writeAppearance syncs legacy ce.theme / ce.density keys", async () => {
    const { writeAppearance, defaultAppearance } = await loadRuntime();
    const storage = createMemoryStorage();

    writeAppearance({ ...defaultAppearance, themeId: "zai-sky", density: "comfortable" }, storage);
    assert.equal(storage.getItem("ce.theme"), "zai-dark");
    assert.equal(storage.getItem("ce.density"), "comfortable");
    const blob = JSON.parse(storage.getItem("ce.appearance"));
    assert.equal(blob.themeId, "zai-sky");
  });

  it("allowlists ce.appearance in UI storage keys", async () => {
    const storageUrl = pathToFileURL(join(root, "src/lib/storage.ts")).href;
    const { UI_STORAGE_KEYS, isAllowedUiStorageKey } = await import(storageUrl);
    assert.equal(UI_STORAGE_KEYS.includes("ce.appearance"), true);
    assert.equal(isAllowedUiStorageKey("ce.appearance"), true);
  });

  it("exposes Workbench Dark/Light catalog labels and Accents themes", async () => {
    const catalogUrl = pathToFileURL(join(root, "src/features/user-preferences/themeCatalog.ts")).href;
    const { themeCatalog, fontFamilies } = await import(catalogUrl);
    const byId = Object.fromEntries(themeCatalog.map((theme) => [theme.id, theme]));
    assert.equal(byId["zai-dark"].name, "Workbench Dark");
    assert.equal(byId["zai-light"].name, "Workbench Light");
    assert.equal(byId["zai-sky"].group, "Accents");
    assert.equal(byId["zai-violet"].group, "Accents");
    assert.equal(byId["zai-emerald"].group, "Accents");
    assert.equal(byId["zai-rose"].group, "Accents");
    assert.deepEqual(
      fontFamilies.map((font) => font.id),
      ["geist", "inter", "system"],
    );
  });

  it("keeps bootstrap script math aligned with runtime helpers", async () => {
    const { effectiveUiScale, binaryThemeId, defaultAppearance } = await loadRuntime();
    const bootstrapUrl = pathToFileURL(join(root, "src/features/user-preferences/appearanceBootstrap.ts")).href;
    const { getAppearanceBootstrapScript } = await import(bootstrapUrl);
    const script = getAppearanceBootstrapScript();

    assert.match(script, /ce\.appearance/);
    assert.match(script, /1\.05/);
    assert.equal(binaryThemeId("zai-sky"), "zai-dark");
    assert.equal(binaryThemeId("zai-light"), "zai-light");
    assert.equal(effectiveUiScale("comfortable", 1.1), 1.155);
    assert.equal(defaultAppearance.fontSize, 13);
    assert.match(script, /"fontSize":13/);
  });
});
