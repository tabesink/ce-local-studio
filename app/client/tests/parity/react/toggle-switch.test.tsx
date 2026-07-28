import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToggleSwitch } from "@/_shared/ui";

function ThemeWrap({
  theme,
  children,
}: {
  theme: "zai-dark" | "zai-light";
  children: ReactNode;
}) {
  return <div data-theme={theme}>{children}</div>;
}

describe("ToggleSwitch parity (R10)", () => {
  it("exposes role=switch with aria-checked when unchecked", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <ToggleSwitch
          checked={false}
          aria-label="Enable notifications"
          onCheckedChange={() => undefined}
        />
      </ThemeWrap>,
    );
    const toggle = screen.getByRole("switch", { name: "Enable notifications" });
    expect(toggle).toHaveAttribute("aria-checked", "false");
  });

  it("exposes aria-checked when checked", () => {
    render(
      <ThemeWrap theme="zai-light">
        <ToggleSwitch
          checked
          aria-label="Disable notifications"
          onCheckedChange={() => undefined}
        />
      </ThemeWrap>,
    );
    expect(screen.getByRole("switch", { name: "Disable notifications" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("toggles via click and keyboard", async () => {
    const user = userEvent.setup();
    const onCheckedChange = vi.fn();
    render(
      <ToggleSwitch
        checked={false}
        aria-label="Enable notifications"
        onCheckedChange={onCheckedChange}
      />,
    );
    const toggle = screen.getByRole("switch", { name: "Enable notifications" });
    await user.click(toggle);
    expect(onCheckedChange).toHaveBeenCalledWith(true);
    toggle.focus();
    await user.keyboard(" ");
    expect(onCheckedChange).toHaveBeenCalledTimes(2);
  });

  it("honors native disabled", () => {
    render(
      <ToggleSwitch
        checked={false}
        disabled
        aria-label="Locked preference"
        onCheckedChange={() => undefined}
      />,
    );
    expect(screen.getByRole("switch", { name: "Locked preference" })).toBeDisabled();
  });
});
