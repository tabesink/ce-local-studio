import { existsSync } from "node:fs";
import path from "node:path";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  applyChatShellStub,
  mockChatShell,
  SYNTHETIC_MESSAGES,
} from "./chat-shell-stubs";

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

describe("Transcript parity (R10)", () => {
  beforeEach(() => {
    applyChatShellStub();
  });

  it("asserts U4 transcript parity trio exists", () => {
    expect(existsSync(path.join(PARITY_ROOT, "manifests", "transcript.json"))).toBe(true);
    expect(existsSync(path.join(PARITY_ROOT, "fixtures", "transcript.html"))).toBe(true);
    expect(existsSync(path.join(PARITY_ROOT, "react", "transcript.test.tsx"))).toBe(true);
  });

  it("renders empty transcript prompt", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <ChatShell />
      </ThemeWrap>,
    );
    expect(screen.getByText("Ask Context Engine to start.")).toBeInTheDocument();
  });

  it("renders synthetic user and assistant thread", () => {
    applyChatShellStub({
      messages: SYNTHETIC_MESSAGES,
      selectedTurnId: "turn_synth_1",
    });
    render(
      <ThemeWrap theme="zai-dark">
        <ChatShell />
      </ThemeWrap>,
    );
    expect(screen.getByText("Synthetic question about valves")).toBeInTheDocument();
    expect(
      screen.getByText("Lorem ipsum grounded answer about valve inspection procedures."),
    ).toBeInTheDocument();
    expect(screen.getByText("2 evidence")).toBeInTheDocument();
  });

  it("selects assistant turn via keyboard", async () => {
    const user = userEvent.setup();
    applyChatShellStub({ messages: SYNTHETIC_MESSAGES });
    render(
      <ThemeWrap theme="zai-light">
        <ChatShell />
      </ThemeWrap>,
    );
    const turn = screen.getByTestId("assistant-turn");
    turn.focus();
    await user.keyboard("{Enter}");
    expect(mockChatShell.selectTurn).toHaveBeenCalledWith("turn_synth_1");
  });

  it("shows loading placeholder while conversation loads", () => {
    applyChatShellStub({ loading: true });
    render(
      <ThemeWrap theme="zai-dark">
        <ChatShell />
      </ThemeWrap>,
    );
    expect(screen.getByText("Loading conversation.")).toBeInTheDocument();
  });

  it("shows redacted notice for redacted turns", () => {
    applyChatShellStub({
      messages: [
        SYNTHETIC_MESSAGES[0],
        {
          ...SYNTHETIC_MESSAGES[1],
          blocks: [],
          status: "redacted",
        },
      ],
    });
    render(
      <ThemeWrap theme="zai-dark">
        <ChatShell />
      </ThemeWrap>,
    );
    expect(screen.getByText("This turn was redacted.")).toBeInTheDocument();
  });
});
