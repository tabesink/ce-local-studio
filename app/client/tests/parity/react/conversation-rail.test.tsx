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

describe("ConversationRail parity (R10)", () => {
  beforeEach(() => {
    applyChatShellStub();
  });

  it("asserts U4 conversation-rail parity trio exists", () => {
    expect(existsSync(path.join(PARITY_ROOT, "manifests", "conversation-rail.json"))).toBe(true);
    expect(existsSync(path.join(PARITY_ROOT, "fixtures", "conversation-rail.html"))).toBe(true);
    expect(existsSync(path.join(PARITY_ROOT, "react", "conversation-rail.test.tsx"))).toBe(true);
  });

  it("renders ready conversation title and header actions", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <ChatShell />
      </ThemeWrap>,
    );
    expect(screen.getAllByText("Valve maintenance notes").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Conversations" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New conversation" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open evidence panel" })).toBeInTheDocument();
  });

  it("shows New conversation when no title is bound", () => {
    applyChatShellStub({ conversation: null });
    render(
      <ThemeWrap theme="zai-light">
        <ChatShell />
      </ThemeWrap>,
    );
    expect(screen.getByText("New conversation")).toBeInTheDocument();
  });

  it("reflects inspector open state on the toggle", () => {
    applyChatShellStub({ panelOpen: true });
    render(
      <ThemeWrap theme="zai-dark">
        <ChatShell />
      </ThemeWrap>,
    );
    expect(screen.getAllByRole("button", { name: "Close evidence panel" })[0]).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("shows stream status pill when reconnecting", () => {
    applyChatShellStub({ streamTransportState: "reconnecting" });
    render(
      <ThemeWrap theme="zai-dark">
        <ChatShell />
      </ThemeWrap>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Reconnecting");
  });

  it("toggles inspector from header control", async () => {
    const user = userEvent.setup();
    applyChatShellStub();
    render(
      <ThemeWrap theme="zai-dark">
        <ChatShell />
      </ThemeWrap>,
    );
    await user.click(screen.getByRole("button", { name: "Open evidence panel" }));
    expect(mockChatShell.setPanelOpen).toHaveBeenCalledWith(true);
  });
});
