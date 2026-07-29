import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { GraphPage } from "@/features/graph/GraphPage";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/dynamic", () => ({
  default: () =>
    function MockGraphCanvas() {
      return <div data-testid="graph-canvas-mock" />;
    },
}));

vi.mock("@/features/domains/api", () => ({
  listMemberDomains: vi.fn(async () => []),
}));

vi.mock("@/features/auth/auth-store", () => ({
  useAuthStore: () => ({
    user: { id: "user-1", username: "mina", role: "member" },
    status: "authenticated",
  }),
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

describe("Graph workbench parity (P12-07 U10)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders empty eligible-domain workbench without unavailable copy", async () => {
    render(
      <ThemeWrap theme="zai-dark">
        <GraphPage />
      </ThemeWrap>,
    );
    await waitFor(() => expect(screen.getByTestId("graph-workbench")).toBeInTheDocument());
    expect(screen.getByText("Knowledge graph")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Graph" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "No eligible domain" })).toBeInTheDocument();
    expect(screen.queryByTestId("graph-unavailable")).not.toBeInTheDocument();
    expect(screen.queryByText(/Graph visualization is not available/i)).not.toBeInTheDocument();
  });

  it("renders under light theme", async () => {
    render(
      <ThemeWrap theme="zai-light">
        <GraphPage />
      </ThemeWrap>,
    );
    await waitFor(() => expect(screen.getByTestId("graph-workbench")).toBeInTheDocument());
    expect(screen.getByText(/Open Documents/i)).toBeInTheDocument();
  });
});
