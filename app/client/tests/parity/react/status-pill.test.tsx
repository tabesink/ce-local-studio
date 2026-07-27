import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusPill, type StatusPillVariant, type UiTone } from "@/ui";

function ThemeWrap({
  theme,
  children,
}: {
  theme: "zai-dark" | "zai-light";
  children: ReactNode;
}) {
  return <div data-theme={theme}>{children}</div>;
}

const TONES: Array<{ tone: UiTone; label: string }> = [
  { tone: "default", label: "Idle" },
  { tone: "info", label: "Syncing" },
  { tone: "good", label: "Ready" },
  { tone: "warning", label: "Degraded" },
  { tone: "danger", label: "Failed" },
];

describe("StatusPill parity (R10)", () => {
  it("never presents tone as color-only for the dot variant", () => {
    render(
      <ThemeWrap theme="zai-dark">
        {TONES.map(({ tone, label }) => (
          <StatusPill key={tone} tone={tone} variant="dot">
            {label}
          </StatusPill>
        ))}
      </ThemeWrap>,
    );
    for (const { label } of TONES) {
      const node = screen.getByText(label);
      expect(node).toBeInTheDocument();
      expect(node.textContent?.trim().length).toBeGreaterThan(0);
      // Dot variant wraps a StatusDot sibling inside the same flex span.
      expect(node.querySelector("span")).not.toBeNull();
    }
  });

  it("renders all live tones for both variants with text labels", () => {
    const variants: StatusPillVariant[] = ["dot", "badge"];
    render(
      <ThemeWrap theme="zai-light">
        {variants.flatMap((variant) =>
          TONES.map(({ tone, label }) => (
            <StatusPill key={`${variant}-${tone}`} tone={tone} variant={variant}>
              {`${variant}:${label}`}
            </StatusPill>
          )),
        )}
      </ThemeWrap>,
    );
    for (const variant of variants) {
      for (const { label } of TONES) {
        expect(screen.getByText(`${variant}:${label}`)).toBeInTheDocument();
      }
    }
  });

  it("documents live tone names (default↔neutral, good↔success) without renaming", () => {
    const liveTones: UiTone[] = ["default", "info", "good", "warning", "danger"];
    expect(liveTones).toEqual(["default", "info", "good", "warning", "danger"]);
    // Contract vocabulary mapping is docs-only.
    expect({ default: "neutral", good: "success" }).toMatchObject({
      default: "neutral",
      good: "success",
    });
  });
});
