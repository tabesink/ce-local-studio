import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { GraphPage } from "@/features/graph/GraphPage";

function ThemeWrap({
  theme,
  children,
}: {
  theme: "zai-dark" | "zai-light";
  children: ReactNode;
}) {
  return <div data-theme={theme}>{children}</div>;
}

describe("Graph unavailable parity (R10)", () => {
  it("renders deliberate unavailable surface with no canvas", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <GraphPage />
      </ThemeWrap>,
    );
    expect(screen.getByTestId("graph-unavailable")).toBeInTheDocument();
    expect(screen.getByText("Knowledge graph")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Graph" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Graph visualization is not available" })).toBeInTheDocument();
    expect(
      screen.getByText(/This page makes no product-data requests/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("canvas")).not.toBeInTheDocument();
  });

  it("renders under light theme without interactive graph controls", () => {
    render(
      <ThemeWrap theme="zai-light">
        <GraphPage />
      </ThemeWrap>,
    );
    expect(screen.getByTestId("graph-unavailable")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });
});
