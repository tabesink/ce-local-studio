import { existsSync } from "node:fs";
import path from "node:path";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  applyChatShellStub,
  mockChatShell,
  SYNTHETIC_EVIDENCE,
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

describe("ChatWorkbench parity (R10)", () => {
  beforeEach(() => {
    applyChatShellStub();
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    });
  });

  it("asserts U4 chat-workbench parity trio exists", () => {
    for (const name of [
      "conversation-rail",
      "transcript",
      "composer",
      "evidence-inspector",
      "chat-workbench",
    ]) {
      expect(existsSync(path.join(PARITY_ROOT, "manifests", `${name}.json`))).toBe(true);
      expect(existsSync(path.join(PARITY_ROOT, "fixtures", `${name}.html`))).toBe(true);
      expect(existsSync(path.join(PARITY_ROOT, "react", `${name}.test.tsx`))).toBe(true);
    }
  });

  it("composes header, transcript, and composer in the main column", () => {
    applyChatShellStub({ messages: SYNTHETIC_MESSAGES });
    render(
      <ThemeWrap theme="zai-dark">
        <ChatShell />
      </ThemeWrap>,
    );
    expect(screen.getAllByText("Valve maintenance notes").length).toBeGreaterThan(0);
    expect(screen.getByText("Synthetic question about valves")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Ask anything — choose a domain for grounded answers"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("complementary", { name: "Evidence" })).not.toBeInTheDocument();
  });

  it("mounts EvidencePanel when inspector is open", () => {
    applyChatShellStub({
      messages: SYNTHETIC_MESSAGES,
      panelOpen: true,
      panelEvidence: SYNTHETIC_EVIDENCE,
      selectedEvidenceId: "ev_synth_1",
      selectedTurnId: "turn_synth_1",
    });
    render(
      <ThemeWrap theme="zai-light">
        <ChatShell />
      </ThemeWrap>,
    );
    expect(screen.getByRole("complementary", { name: "Evidence" })).toBeInTheDocument();
    expect(screen.getByText("(2)")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-card-ev_synth_1")).toBeInTheDocument();
  });

  it("shows empty workbench state without messages", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <ChatShell />
      </ThemeWrap>,
    );
    expect(screen.getByText("Ask Context Engine to start.")).toBeInTheDocument();
    expect(screen.getByText("direct chat")).toBeInTheDocument();
  });
});
