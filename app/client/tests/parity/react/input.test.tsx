import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Input } from "@/ui";

function ThemeWrap({
  theme,
  children,
}: {
  theme: "zai-dark" | "zai-light";
  children: ReactNode;
}) {
  return <div data-theme={theme}>{children}</div>;
}

describe("Input parity (R10)", () => {
  it("associates label with the control when label is provided", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <Input label="Display name" placeholder="Enter a display name" />
      </ThemeWrap>,
    );
    const input = screen.getByLabelText("Display name");
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute("id", "display-name");
  });

  it("shows error text when error is provided", () => {
    render(
      <ThemeWrap theme="zai-light">
        <Input label="Display name" error="Display name is required" />
      </ThemeWrap>,
    );
    expect(screen.getByText("Display name is required")).toBeInTheDocument();
  });

  it("supports native disabled", () => {
    render(<Input label="Display name" disabled defaultValue="Locked value" />);
    expect(screen.getByLabelText("Display name")).toBeDisabled();
  });

  it("is focusable when enabled", async () => {
    const user = userEvent.setup();
    render(<Input label="Display name" />);
    const input = screen.getByLabelText("Display name");
    await user.click(input);
    expect(input).toHaveFocus();
  });

  it("accepts keyboard entry (live Input has no help prop)", async () => {
    const user = userEvent.setup();
    render(<Input label="Display name" />);
    const input = screen.getByLabelText("Display name");
    await user.type(input, "Synthetic user");
    expect(input).toHaveValue("Synthetic user");
    // Approved gap: help remains nearby composition, not a prop on Input.
    expect(screen.queryByText(/help/i)).not.toBeInTheDocument();
  });
});
