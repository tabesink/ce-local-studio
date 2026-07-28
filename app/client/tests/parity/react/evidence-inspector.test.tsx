import { existsSync } from "node:fs";
import path from "node:path";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EvidencePanel } from "@/features/chat-shell/EvidencePanel";
import {
  SYNTHETIC_ACCEPTED_REFS,
  SYNTHETIC_EVIDENCE,
} from "./chat-shell-stubs";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
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

describe("EvidenceInspector parity (R10)", () => {
  beforeEach(() => {
    push.mockReset();
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query === "(max-width: 1023px)" ? false : false,
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    });
  });

  it("asserts U4 evidence-inspector parity trio exists", () => {
    expect(existsSync(path.join(PARITY_ROOT, "manifests", "evidence-inspector.json"))).toBe(true);
    expect(existsSync(path.join(PARITY_ROOT, "fixtures", "evidence-inspector.html"))).toBe(true);
    expect(existsSync(path.join(PARITY_ROOT, "react", "evidence-inspector.test.tsx"))).toBe(true);
  });

  it("renders Evidence | Refs | Source tabs with synthetic cards", async () => {
    const user = userEvent.setup();
    render(
      <ThemeWrap theme="zai-dark">
        <EvidencePanel
          open
          rows={SYNTHETIC_EVIDENCE}
          acceptedRefs={SYNTHETIC_ACCEPTED_REFS}
          selectedEvidenceId="ev_synth_1"
          onSelectEvidence={vi.fn()}
          onClose={vi.fn()}
        />
      </ThemeWrap>,
    );

    expect(screen.getByRole("complementary", { name: "Evidence" })).toBeInTheDocument();
    expect(screen.getByText("(2)")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-card-ev_synth_1")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getAllByText("Valve handbook").length).toBeGreaterThan(0);

    await user.click(screen.getByTestId("inspector-tab-refs"));
    expect(screen.getByText("Handbook excerpt")).toBeInTheDocument();

    await user.click(screen.getByTestId("inspector-tab-source"));
    expect(screen.getByTestId("open-in-library")).toBeEnabled();
  });

  it("shows contextual empty states", async () => {
    const user = userEvent.setup();
    render(
      <ThemeWrap theme="zai-light">
        <EvidencePanel
          open
          rows={[]}
          acceptedRefs={[]}
          selectedEvidenceId={null}
          onSelectEvidence={vi.fn()}
          onClose={vi.fn()}
        />
      </ThemeWrap>,
    );

    expect(screen.getByText(/Retrieved evidence for this answer/i)).toBeInTheDocument();
    await user.click(screen.getByTestId("inspector-tab-refs"));
    expect(screen.getByText(/Accepted references for this turn/i)).toBeInTheDocument();
  });

  it("activates evidence cards with keyboard Enter", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <ThemeWrap theme="zai-dark">
        <EvidencePanel
          open
          rows={SYNTHETIC_EVIDENCE}
          acceptedRefs={[]}
          selectedEvidenceId={null}
          onSelectEvidence={onSelect}
          onClose={vi.fn()}
        />
      </ThemeWrap>,
    );

    const card = screen.getByTestId("evidence-card-ev_synth_1");
    card.focus();
    await user.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledWith("ev_synth_1");
  });

  it("renders narrow drawer dialog when matchMedia matches", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation((query: string) => ({
        matches: query === "(max-width: 1023px)",
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    );

    render(
      <ThemeWrap theme="zai-dark">
        <EvidencePanel
          open
          rows={SYNTHETIC_EVIDENCE}
          acceptedRefs={[]}
          selectedEvidenceId="ev_synth_1"
          onSelectEvidence={vi.fn()}
          onClose={vi.fn()}
        />
      </ThemeWrap>,
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getAllByLabelText("Close evidence panel").length).toBeGreaterThan(0);
    vi.unstubAllGlobals();
  });

  it("returns null when inspector is closed", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <EvidencePanel
          open={false}
          rows={SYNTHETIC_EVIDENCE}
          acceptedRefs={[]}
          selectedEvidenceId={null}
          onSelectEvidence={vi.fn()}
          onClose={vi.fn()}
        />
      </ThemeWrap>,
    );
    expect(screen.queryByRole("complementary", { name: "Evidence" })).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
