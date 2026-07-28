import { existsSync } from "node:fs";
import path from "node:path";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AppShell } from "@/features/shell/AppShell";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/chat",
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: ReactNode;
    href: string;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/features/auth/auth-store", () => ({
  useAuthStore: (selector: (state: unknown) => unknown) =>
    selector({
      user: { role: "member" },
      logout: vi.fn().mockResolvedValue(undefined),
    }),
}));

vi.mock("@/features/chat-shell/api", () => ({
  listConversations: vi.fn().mockResolvedValue([]),
}));

const PARITY_ROOT = path.resolve(__dirname, "..");

function ThemeWrap({
  theme,
  children,
}: {
  theme: "zai-dark" | "zai-light";
  children: ReactNode;
}) {
  return <div data-theme={theme}>{children}</div>;
}

describe("AppShell parity (R10)", () => {
  beforeEach(() => {
    localStorage.clear();
    push.mockReset();
  });

  it("asserts U3 shell parity trios exist", () => {
    for (const name of ["app-shell", "navigation-rail", "pane-header"]) {
      expect(existsSync(path.join(PARITY_ROOT, "manifests", `${name}.json`))).toBe(true);
      expect(existsSync(path.join(PARITY_ROOT, "fixtures", `${name}.html`))).toBe(true);
      expect(existsSync(path.join(PARITY_ROOT, "react", `${name}.test.tsx`))).toBe(true);
    }
  });

  it("renders main landmark with route children", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <AppShell>
          <p>Primary workspace</p>
        </AppShell>
      </ThemeWrap>,
    );
    const main = screen.getByRole("main");
    expect(main).toHaveTextContent("Primary workspace");
    expect(main.className).toMatch(/flex-1/);
  });

  it("composes expanded navigation rail with application nav", () => {
    render(
      <ThemeWrap theme="zai-light">
        <AppShell>
          <p>Primary workspace</p>
        </AppShell>
      </ThemeWrap>,
    );
    expect(screen.getByRole("navigation", { name: "Application" })).toBeInTheDocument();
    expect(screen.getByLabelText("Chat")).toBeInTheDocument();
  });

  it("exposes mobile navigation menu affordance", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <AppShell>
          <p>Primary workspace</p>
        </AppShell>
      </ThemeWrap>,
    );
    expect(screen.getByRole("button", { name: "Open navigation menu" })).toBeInTheDocument();
  });
});
