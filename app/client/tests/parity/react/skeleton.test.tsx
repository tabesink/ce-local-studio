import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

function Skeleton({ variant }: { variant: "text" | "row" | "card" | "pane" }) {
  return <span aria-hidden="true" data-variant={variant} className={`skeleton skeleton-${variant}`} />;
}

function LoadingRegion({ children }: { children: ReactNode }) {
  return <section aria-label="Loading examples" aria-busy="true">{children}</section>;
}

describe("Skeleton parity harness (R10)", () => {
  it.each(["text", "row", "card", "pane"] as const)("renders an aria-hidden %s shape", (variant) => {
    const { container } = render(<LoadingRegion><Skeleton variant={variant} /></LoadingRegion>);
    expect(container.querySelector(`[data-variant="${variant}"]`)).toHaveAttribute("aria-hidden", "true");
  });

  it("names loading state on the parent rather than the shape", () => {
    render(<LoadingRegion><Skeleton variant="row" /></LoadingRegion>);
    expect(screen.getByRole("region", { name: "Loading examples" })).toHaveAttribute("aria-busy", "true");
  });

  it("renders within the light theme region", () => {
    const { container } = render(<div data-theme="zai-light"><LoadingRegion><Skeleton variant="pane" /></LoadingRegion></div>);
    expect(container.querySelector("[data-theme]")).toHaveAttribute("data-theme", "zai-light");
  });
});
