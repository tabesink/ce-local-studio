import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EvidencePanel } from "@/features/chat-shell/EvidencePanel";
import type { EvidenceRow } from "@/features/chat-shell/types";
import type { AcceptedRef } from "@/features/chat-shell/api";
import { buildDocumentsDeepLinkHref } from "@/features/chat-shell/documentsDeepLink";

const evidence: EvidenceRow[] = [
  {
    id: "ev_safe_12",
    citationLabel: "1",
    sourceLabel: "Policy handbook",
    documentLabel: "Policy handbook",
    documentRef: "doc_safe_7",
    excerpt: "Members may query one authorized domain.",
    kind: "text",
    anchor: {
      pageNumber: 18,
      fallback: "page",
      region: null,
      sectionLabel: "Eligibility",
    },
  },
];

const acceptedRefs: AcceptedRef[] = [
  {
    id: "aref_1",
    kind: "source",
    label: "Handbook",
    description: "Selected source",
    order: 1,
  },
];

function ThemeWrap({ children }: { children: ReactNode }) {
  return <div data-theme="zai-dark">{children}</div>;
}

describe("chat inspector workbench (P9-02 U5)", () => {
  it("exposes Evidence | Refs | Source tabs with empty and populated states", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const onClose = vi.fn();

    render(
      <ThemeWrap>
        <EvidencePanel
          open
          rows={evidence}
          acceptedRefs={acceptedRefs}
          selectedEvidenceId="ev_safe_12"
          onSelectEvidence={onSelect}
          onClose={onClose}
        />
      </ThemeWrap>,
    );

    expect(screen.getByTestId("inspector-tab-evidence")).toBeInTheDocument();
    expect(screen.getByTestId("inspector-tab-refs")).toBeInTheDocument();
    expect(screen.getByTestId("inspector-tab-source")).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "Evidence" })).toBeInTheDocument();

    const evidenceCard = screen.getByTestId("evidence-card-ev_safe_12");
    expect(evidenceCard).toHaveAttribute("aria-pressed", "true");
    await user.click(evidenceCard);
    expect(onSelect).toHaveBeenCalledWith("ev_safe_12");

    await user.click(screen.getByTestId("inspector-tab-refs"));
    expect(screen.getByText("Handbook")).toBeInTheDocument();

    await user.click(screen.getByTestId("inspector-tab-source"));
    expect(screen.getByTestId("open-in-library")).toBeDisabled();
    expect(screen.getByTestId("document-navigation-unavailable")).toHaveTextContent(
      /Library preview surface is ready|unavailable/i,
    );

    const href = buildDocumentsDeepLinkHref({
      documentRef: evidence[0].documentRef,
      evidenceRef: evidence[0].id,
      page: evidence[0].anchor.pageNumber,
    });
    expect(href).toBe("/documents?document=doc_safe_7&evidence=ev_safe_12&page=18");
  });

  it("shows contextual empty states when a turn has no evidence or refs", async () => {
    const user = userEvent.setup();
    render(
      <ThemeWrap>
        <EvidencePanel
          open
          rows={[]}
          acceptedRefs={[]}
          selectedEvidenceId={null}
          onSelectEvidence={() => undefined}
          onClose={() => undefined}
        />
      </ThemeWrap>,
    );

    expect(screen.getByText(/Retrieved evidence for this answer/i)).toBeInTheDocument();
    await user.click(screen.getByTestId("inspector-tab-refs"));
    expect(screen.getByText(/Accepted references for this turn/i)).toBeInTheDocument();
    await user.click(screen.getByTestId("inspector-tab-source"));
    expect(screen.getByText(/Select evidence to view/i)).toBeInTheDocument();
  });

  it("activates evidence cards with keyboard Enter/Space", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <ThemeWrap>
        <EvidencePanel
          open
          rows={evidence}
          acceptedRefs={[]}
          selectedEvidenceId={null}
          onSelectEvidence={onSelect}
          onClose={() => undefined}
        />
      </ThemeWrap>,
    );

    const card = screen.getByTestId("evidence-card-ev_safe_12");
    card.focus();
    await user.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledWith("ev_safe_12");
    onSelect.mockClear();
    card.focus();
    await user.keyboard(" ");
    expect(onSelect).toHaveBeenCalledWith("ev_safe_12");
  });
});
