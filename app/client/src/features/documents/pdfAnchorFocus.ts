/**
 * Normalized crop-box region → CSS overlay geometry for the PDF canvas.
 * Origin is top-left of the unrotated page; values are clamped to [0, 1].
 */

export type NormalizedRegion = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type CssRect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

export type AnchorFallback = "region" | "section" | "page";

const EPSILON = 1e-9;

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Reject incomplete or out-of-page regions; clamp tiny float noise into bounds. */
export function clampNormalizedRegion(region: NormalizedRegion | null | undefined): NormalizedRegion | null {
  if (!region) return null;
  const x = Number(region.x);
  const y = Number(region.y);
  const width = Number(region.width);
  const height = Number(region.height);
  if (![x, y, width, height].every((value) => Number.isFinite(value))) return null;
  if (width <= 0 || height <= 0) return null;
  if (x < -EPSILON || y < -EPSILON || x + width > 1 + EPSILON || y + height > 1 + EPSILON) {
    return null;
  }
  const clampedX = Math.min(1, Math.max(0, x));
  const clampedY = Math.min(1, Math.max(0, y));
  const clampedWidth = Math.min(1 - clampedX, Math.max(0, width));
  const clampedHeight = Math.min(1 - clampedY, Math.max(0, height));
  if (clampedWidth <= 0 || clampedHeight <= 0) return null;
  return { x: clampedX, y: clampedY, width: clampedWidth, height: clampedHeight };
}

/**
 * Map a normalized crop-box rect onto canvas pixels after scale and clockwise rotation.
 * `rotation` is degrees in {0, 90, 180, 270}.
 */
export function regionToCssRect(
  region: NormalizedRegion | null | undefined,
  options: {
    canvasWidth: number;
    canvasHeight: number;
    rotation?: number;
  },
): CssRect | null {
  const clamped = clampNormalizedRegion(region);
  const canvasWidth = options.canvasWidth;
  const canvasHeight = options.canvasHeight;
  const rotation = options.rotation ?? 0;
  if (!clamped || canvasWidth <= 0 || canvasHeight <= 0) return null;

  const norm = ((rotation % 360) + 360) % 360;
  const { x, y, width, height } = clamped;

  const px = (value: number) => Math.round(value * 1000) / 1000;

  if (norm === 0) {
    return {
      left: px(x * canvasWidth),
      top: px(y * canvasHeight),
      width: px(width * canvasWidth),
      height: px(height * canvasHeight),
    };
  }
  if (norm === 90) {
    return {
      left: px((1 - y - height) * canvasWidth),
      top: px(x * canvasHeight),
      width: px(height * canvasWidth),
      height: px(width * canvasHeight),
    };
  }
  if (norm === 180) {
    return {
      left: px((1 - x - width) * canvasWidth),
      top: px((1 - y - height) * canvasHeight),
      width: px(width * canvasWidth),
      height: px(height * canvasHeight),
    };
  }
  if (norm === 270) {
    return {
      left: px(y * canvasWidth),
      top: px((1 - x - width) * canvasHeight),
      width: px(height * canvasWidth),
      height: px(width * canvasHeight),
    };
  }
  return null;
}

/** Soft containing-block cue when a figure/table has page but no proven region. */
export function containingBlockCssRect(canvasWidth: number, canvasHeight: number): CssRect | null {
  if (canvasWidth <= 0 || canvasHeight <= 0) return null;
  const insetX = canvasWidth * 0.06;
  const insetY = canvasHeight * 0.06;
  return {
    left: insetX,
    top: insetY,
    width: Math.max(0, canvasWidth - insetX * 2),
    height: Math.max(0, canvasHeight - insetY * 2),
  };
}

export function resolveHighlightRect(options: {
  region: NormalizedRegion | null | undefined;
  fallback: AnchorFallback;
  evidenceKind?: string | null;
  canvasWidth: number;
  canvasHeight: number;
  rotation?: number;
}): { rect: CssRect; mode: "region" | "containing-block" } | null {
  const regionRect = regionToCssRect(options.region ?? null, {
    canvasWidth: options.canvasWidth,
    canvasHeight: options.canvasHeight,
    rotation: options.rotation ?? 0,
  });
  if (regionRect && options.fallback === "region") {
    return { rect: regionRect, mode: "region" };
  }
  if (regionRect) {
    return { rect: regionRect, mode: "region" };
  }
  const kind = options.evidenceKind ?? "";
  if (
    options.fallback !== "page" &&
    (kind === "figure" || kind === "table") &&
    !clampNormalizedRegion(options.region)
  ) {
    const block = containingBlockCssRect(options.canvasWidth, options.canvasHeight);
    if (block) return { rect: block, mode: "containing-block" };
  }
  return null;
}

export function focusAnnouncement(options: {
  evidenceKind?: string | null;
  pageNumber: number;
  sectionLabel?: string | null;
  mode: "region" | "containing-block" | "section" | "page" | null;
}): string {
  const kind = options.evidenceKind === "table" ? "Table" : options.evidenceKind === "figure" ? "Figure" : "Evidence";
  if (options.mode === "region") {
    return `${kind} on page ${options.pageNumber} focused.`;
  }
  if (options.mode === "containing-block") {
    return `${kind} area on page ${options.pageNumber} focused.`;
  }
  if (options.mode === "section" && options.sectionLabel) {
    return `${options.sectionLabel} on page ${options.pageNumber}.`;
  }
  return `Page ${options.pageNumber}.`;
}
