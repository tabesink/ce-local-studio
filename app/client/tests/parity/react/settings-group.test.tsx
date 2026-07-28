import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SettingsGroup } from "@/_shared/ui";
import { StatusPill } from "@/ui";
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

describe("Settings group parity (R10)", () => {
  it("renders group title, description, and bordered row stack", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <SettingsGroup
          title="Providers"
          description="Credentials are write-only; values are never displayed."
        >
          <SettingsRow
            label="Synthetic provider A"
            status={<StatusPill tone="good">Configured</StatusPill>}
          />
          <SettingsRow
            label="Synthetic provider B"
            status={<StatusPill tone="warning">Not configured</StatusPill>}
          />
        </SettingsGroup>
      </ThemeWrap>,
    );
    expect(screen.getByText("Providers")).toBeInTheDocument();
    expect(
      screen.getByText("Credentials are write-only; values are never displayed."),
    ).toBeInTheDocument();
    expect(screen.getByText("Synthetic provider A")).toBeInTheDocument();
    expect(screen.getByText("Configured")).toBeInTheDocument();
    expect(screen.getByText("Not configured")).toBeInTheDocument();
  });

  it("hosts settings rows without duplicating domain accordion", () => {
    render(
      <ThemeWrap theme="zai-light">
        <SettingsGroup title="Users" description="Read-only account status.">
          <SettingsRow
            label="Synthetic Member"
            value={<span>member</span>}
            status={<StatusPill tone="good">Active</StatusPill>}
          />
        </SettingsGroup>
      </ThemeWrap>,
    );
    expect(screen.getByText("Users")).toBeInTheDocument();
    expect(screen.getByText("Synthetic Member")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Expand Synthetic/i })).not.toBeInTheDocument();
  });
});
