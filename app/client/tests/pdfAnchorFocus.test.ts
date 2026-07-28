import { afterEach, describe, expect, it, vi } from "vitest";
import {
  clampNormalizedRegion,
  containingBlockCssRect,
  prefersReducedMotion,
  regionToCssRect,
  resolveHighlightRect,
} from "@/features/documents/pdfAnchorFocus";

describe("pdfAnchorFocus (P4-05 U4)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("clamps and rejects invalid normalized regions", () => {
    expect(
      clampNormalizedRegion({ x: 0.12, y: 0.24, width: 0.66, height: 0.41 }),
    ).toEqual({ x: 0.12, y: 0.24, width: 0.66, height: 0.41 });
    expect(clampNormalizedRegion({ x: 0.9, y: 0.9, width: 0.5, height: 0.5 })).toBeNull();
    expect(clampNormalizedRegion({ x: 0, y: 0, width: 0, height: 0.5 })).toBeNull();
  });

  it("maps regions through rotation and non-default canvas size (zoom)", () => {
    const region = { x: 0.1, y: 0.2, width: 0.3, height: 0.4 };
    expect(regionToCssRect(region, { canvasWidth: 200, canvasHeight: 100, rotation: 0 })).toEqual({
      left: 20,
      top: 20,
      width: 60,
      height: 40,
    });
    expect(regionToCssRect(region, { canvasWidth: 200, canvasHeight: 100, rotation: 180 })).toEqual({
      left: 120,
      top: 40,
      width: 60,
      height: 40,
    });
    const zoomed = regionToCssRect(region, { canvasWidth: 400, canvasHeight: 200, rotation: 0 });
    expect(zoomed).toEqual({ left: 40, top: 40, width: 120, height: 80 });
  });

  it("uses containing-block cue for figure without region before page-only", () => {
    const resolved = resolveHighlightRect({
      region: null,
      fallback: "section",
      evidenceKind: "figure",
      canvasWidth: 200,
      canvasHeight: 100,
    });
    expect(resolved?.mode).toBe("containing-block");
    expect(resolved?.rect).toEqual(containingBlockCssRect(200, 100));
    expect(
      resolveHighlightRect({
        region: null,
        fallback: "page",
        evidenceKind: "figure",
        canvasWidth: 200,
        canvasHeight: 100,
      }),
    ).toBeNull();
  });

  it("honors prefers-reduced-motion for scroll behavior callers", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation((query: string) => ({
        matches: query === "(prefers-reduced-motion: reduce)",
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    );
    expect(prefersReducedMotion()).toBe(true);
  });
});
