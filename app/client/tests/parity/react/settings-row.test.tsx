import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button, StatusPill } from "@/ui";
import { SettingsRow } from "@/features/settings-panel/SettingsRow";

function ThemeWrap({
  theme,
  children,
}: {
  theme: "zai-dark" | "zai-light";
  children: ReactNode;
}) {
  return <div data-theme={theme}>{children}</div>;
}

describe("SettingsRow parity (R10)", () => {
  it("renders the row label", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <SettingsRow label="Notification preference" />
      </ThemeWrap>,
    );
    expect(screen.getByText("Notification preference")).toBeInTheDocument();
  });

  it("keeps an actionable control keyboard-focusable", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <ThemeWrap theme="zai-light">
        <SettingsRow
          label="Notification preference"
          description="Synthetic preference description for parity only"
          control={
            <Button variant="secondary" onClick={onClick}>
              Edit
            </Button>
          }
        />
      </ThemeWrap>,
    );
    const control = screen.getByRole("button", { name: "Edit" });
    control.focus();
    expect(control).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("can host StatusPill in the status slot", () => {
    render(
      <SettingsRow
        label="Notification preference"
        status={<StatusPill tone="good">Ready</StatusPill>}
      />,
    );
    expect(screen.getByText("Notification preference")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
  });
});
