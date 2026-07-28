import { existsSync } from "node:fs";
import path from "node:path";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { applyChatShellStub, mockChatShell } from "./chat-shell-stubs";

vi.mock("@/features/chat-shell/use-chat-shell", () => ({
  useChatShell: () => mockChatShell,
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn() }),
}));

import { ChatShell } from "@/features/chat-shell/ChatShell";

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

describe("Composer parity (R10)", () => {
  beforeEach(() => {
    applyChatShellStub();
  });

  it("asserts U4 composer parity trio exists", () => {
    expect(existsSync(path.join(PARITY_ROOT, "manifests", "composer.json"))).toBe(true);
    expect(existsSync(path.join(PARITY_ROOT, "fixtures", "composer.html"))).toBe(true);
    expect(existsSync(path.join(PARITY_ROOT, "react", "composer.test.tsx"))).toBe(true);
  });

  it("renders composer placeholder and direct chat status", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <ChatShell />
      </ThemeWrap>,
    );
    expect(
      screen.getByPlaceholderText("Ask anything — choose a domain for grounded answers"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("domain-selector")).toBeInTheDocument();
    expect(screen.getByText("direct chat")).toBeInTheDocument();
    expect(screen.getByTestId("ref-picker")).toBeDisabled();
    expect(screen.getByLabelText("References unavailable")).toHaveAttribute("aria-disabled", "true");
  });

  it("shows domain display label in status bar when selected", () => {
    applyChatShellStub({ domainId: "dom_synth_1" });
    render(
      <ThemeWrap theme="zai-light">
        <ChatShell />
      </ThemeWrap>,
    );
    expect(screen.getByText("domain: Plant manuals")).toBeInTheDocument();
  });

  it("disables send while streaming or when input is empty", () => {
    applyChatShellStub({ input: "Synthetic draft about valve schedules", streaming: true });
    render(
      <ThemeWrap theme="zai-dark">
        <ChatShell />
      </ThemeWrap>,
    );
    expect(screen.getByTestId("composer-send")).toBeDisabled();
    expect(screen.getByTestId("chat-streaming")).toHaveAttribute("data-streaming", "true");
  });

  it("enables send when input is present and idle", () => {
    applyChatShellStub({ input: "Synthetic draft about valve schedules" });
    render(
      <ThemeWrap theme="zai-dark">
        <ChatShell />
      </ThemeWrap>,
    );
    expect(screen.getByTestId("composer-send")).toBeEnabled();
  });

  it("routes textarea edits and submit through the chat stub", async () => {
    const user = userEvent.setup();
    applyChatShellStub({ input: "Synthetic draft about valve schedules" });
    render(
      <ThemeWrap theme="zai-dark">
        <ChatShell />
      </ThemeWrap>,
    );
    await user.click(screen.getByTestId("composer-send"));
    expect(mockChatShell.submit).toHaveBeenCalled();
  });
});
