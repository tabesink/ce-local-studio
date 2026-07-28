import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NavigationSidebar } from "@/features/navigation-sidebar/NavigationSidebar";

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

function ThemeWrap({
  theme,
  children,
}: {
  theme: "zai-dark" | "zai-light";
  children: ReactNode;
}) {
  return <div data-theme={theme}>{children}</div>;
}

describe("NavigationRail parity (R10)", () => {
  beforeEach(() => {
    localStorage.clear();
    push.mockReset();
  });

  it("renders expanded workspace routes and settings footer", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <NavigationSidebar />
      </ThemeWrap>,
    );
    expect(screen.getByText("Workspace")).toBeInTheDocument();
    expect(screen.getByLabelText("Chat")).toBeInTheDocument();
    expect(screen.getByLabelText("Library")).toBeInTheDocument();
    expect(screen.getByLabelText("Settings")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Collapse sidebar" })).toBeInTheDocument();
  });

  it("collapses the desktop rail and exposes the expand control", async () => {
    const user = userEvent.setup();
    render(
      <ThemeWrap theme="zai-dark">
        <NavigationSidebar />
      </ThemeWrap>,
    );
    await user.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    expect(screen.queryByRole("navigation", { name: "Application" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Expand sidebar" })).toBeInTheDocument();
  });

  it("restores the application nav when expanded again", async () => {
    const user = userEvent.setup();
    render(
      <ThemeWrap theme="zai-light">
        <NavigationSidebar />
      </ThemeWrap>,
    );
    await user.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    await user.click(screen.getByRole("button", { name: "Expand sidebar" }));
    expect(screen.getByRole("navigation", { name: "Application" })).toBeInTheDocument();
  });

  it("opens the mobile drawer from the top bar menu button", async () => {
    const user = userEvent.setup();
    render(
      <ThemeWrap theme="zai-dark">
        <NavigationSidebar />
      </ThemeWrap>,
    );
    const menu = screen.getByRole("button", { name: "Open navigation menu" });
    await user.click(menu);
    expect(menu).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Navigation")).toBeInTheDocument();
  });
});
