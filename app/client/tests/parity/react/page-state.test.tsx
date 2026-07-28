import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { PageState } from "@/components/ui/PageState";

function ThemeWrap({
  theme,
  children,
}: {
  theme: "zai-dark" | "zai-light";
  children: ReactNode;
}) {
  return <div data-theme={theme}>{children}</div>;
}

describe("PageState parity (R10)", () => {
  it("renders default tone title and message", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <PageState title="Loading" message="Resolving session." />
      </ThemeWrap>,
    );
    expect(screen.getByRole("heading", { name: "Loading" })).toBeInTheDocument();
    expect(screen.getByText("Resolving session.")).toBeInTheDocument();
  });

  it("renders danger tone title and message", () => {
    render(
      <ThemeWrap theme="zai-light">
        <PageState
          tone="danger"
          title="Forbidden"
          message="You do not have access to this surface."
        />
      </ThemeWrap>,
    );
    expect(screen.getByRole("heading", { name: "Forbidden" })).toBeInTheDocument();
    expect(screen.getByText("You do not have access to this surface.")).toBeInTheDocument();
  });

  it("uses h1 for the title in both tones", () => {
    const { rerender } = render(<PageState title="Loading" message="Resolving session." />);
    expect(screen.getByRole("heading", { level: 1, name: "Loading" })).toBeInTheDocument();
    rerender(
      <PageState
        tone="danger"
        title="Forbidden"
        message="You do not have access to this surface."
      />,
    );
    expect(screen.getByRole("heading", { level: 1, name: "Forbidden" })).toBeInTheDocument();
  });
});
