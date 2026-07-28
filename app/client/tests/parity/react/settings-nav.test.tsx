import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Database, KeyRound, Palette, Users } from "lucide-react";
import { SettingsLayout } from "@/_shared/ui";

function ThemeWrap({
  theme,
  children,
}: {
  theme: "zai-dark" | "zai-light";
  children: ReactNode;
}) {
  return <div data-theme={theme}>{children}</div>;
}

const memberSections = [
  {
    id: "general" as const,
    label: "General",
    description: "Personal preferences",
    icon: <Palette className="h-3.5 w-3.5" />,
  },
];

const adminSections = [
  ...memberSections,
  {
    id: "provider" as const,
    label: "Model Provider",
    description: "Providers and model profiles",
    icon: <KeyRound className="h-3.5 w-3.5" />,
  },
  {
    id: "domains" as const,
    label: "Knowledge Domains",
    description: "Domain-backed retrieval",
    icon: <Database className="h-3.5 w-3.5" />,
  },
  {
    id: "users" as const,
    label: "Users",
    description: "User accounts",
    icon: <Users className="h-3.5 w-3.5" />,
  },
];

describe("Settings nav parity (R10)", () => {
  it("renders member General section as active", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <SettingsLayout
          sections={memberSections}
          activeSection="general"
          title="Settings"
          status=""
          loading={false}
          onReload={vi.fn()}
          onSelectSection={vi.fn()}
        >
          <p>Personal preferences content</p>
        </SettingsLayout>
      </ThemeWrap>,
    );
    expect(screen.getByRole("heading", { level: 1, name: "Settings" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Settings sections" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "General" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "General" })).toBeInTheDocument();
  });

  it("renders administrator section list with Model Provider active", () => {
    render(
      <ThemeWrap theme="zai-light">
        <SettingsLayout
          sections={adminSections}
          activeSection="provider"
          title="Settings"
          status=""
          loading={false}
          onReload={vi.fn()}
          onSelectSection={vi.fn()}
        >
          <p>Provider content</p>
        </SettingsLayout>
      </ThemeWrap>,
    );
    expect(screen.getByRole("button", { name: "Model Provider" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Knowledge Domains" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Users" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Model Provider" })).toBeInTheDocument();
  });

  it("keeps section buttons keyboard-focusable and activatable", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <ThemeWrap theme="zai-dark">
        <SettingsLayout
          sections={adminSections}
          activeSection="general"
          title="Settings"
          status=""
          loading={false}
          onReload={vi.fn()}
          onSelectSection={onSelect}
        >
          <p>Content</p>
        </SettingsLayout>
      </ThemeWrap>,
    );
    const provider = screen.getByRole("button", { name: "Model Provider" });
    provider.focus();
    expect(provider).toHaveFocus();
    await user.click(provider);
    expect(onSelect).toHaveBeenCalledWith("provider");
  });
});
