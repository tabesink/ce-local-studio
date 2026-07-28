import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PageHeader } from "@/_shared/ui";

function ThemeWrap({
  theme,
  children,
}: {
  theme: "zai-dark" | "zai-light";
  children: ReactNode;
}) {
  return <div data-theme={theme}>{children}</div>;
}

describe("Pane header parity (R10)", () => {
  it("renders eyebrow and title as the route pane header", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <PageHeader eyebrow="Workspace" title="Primary surface" />
      </ThemeWrap>,
    );
    expect(screen.getByText("Workspace")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Primary surface" })).toBeInTheDocument();
  });

  it("renders trailing actions and keeps them keyboard-focusable", async () => {
    const user = userEvent.setup();
    const onFilter = vi.fn();
    render(
      <ThemeWrap theme="zai-light">
        <PageHeader
          title="Primary surface"
          actions={
            <>
              <button type="button" onClick={onFilter}>
                Filter
              </button>
              <button type="button">New item</button>
            </>
          }
        />
      </ThemeWrap>,
    );
    const filter = screen.getByRole("button", { name: "Filter" });
    expect(screen.getByRole("button", { name: "New item" })).toBeInTheDocument();
    filter.focus();
    expect(filter).toHaveFocus();
    await user.click(filter);
    expect(onFilter).toHaveBeenCalledOnce();
  });

  it("documents pane-header geometry via title-only variant", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <PageHeader title="Primary surface" />
      </ThemeWrap>,
    );
    expect(screen.getByRole("heading", { name: "Primary surface" })).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
