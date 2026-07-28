import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Select } from "@/_shared/ui";

function ThemeWrap({
  theme,
  children,
}: {
  theme: "zai-dark" | "zai-light";
  children: ReactNode;
}) {
  return <div data-theme={theme}>{children}</div>;
}

const FONT_OPTIONS = [
  { value: "system", label: "System default" },
  { value: "geist", label: "Geist Sans" },
];

describe("Select parity (R10)", () => {
  it("associates label with the control when label is provided", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <Select label="Font family" options={FONT_OPTIONS} defaultValue="system" />
      </ThemeWrap>,
    );
    const select = screen.getByLabelText("Font family");
    expect(select).toBeInTheDocument();
    expect(select).toHaveAttribute("id", "font-family");
  });

  it("renders synthetic options", () => {
    render(
      <ThemeWrap theme="zai-light">
        <Select
          label="Font family"
          placeholder="Choose a font"
          options={FONT_OPTIONS}
          defaultValue=""
        />
      </ThemeWrap>,
    );
    expect(screen.getByRole("option", { name: "Choose a font" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "System default" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Geist Sans" })).toBeInTheDocument();
  });

  it("supports native disabled", () => {
    render(
      <Select
        label="Font family"
        options={[{ value: "locked", label: "Locked selection" }]}
        disabled
        defaultValue="locked"
      />,
    );
    expect(screen.getByLabelText("Font family")).toBeDisabled();
  });

  it("is focusable when enabled", async () => {
    const user = userEvent.setup();
    render(<Select aria-label="Font family" options={FONT_OPTIONS} defaultValue="system" />);
    const select = screen.getByLabelText("Font family");
    await user.click(select);
    expect(select).toHaveFocus();
  });
});
