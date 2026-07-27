import { useState, type ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToggleSwitch } from "@/components/ui";
import { DomainAccordionRow } from "@/features/settings-panel/DomainAccordionRow";
import { nextExpandedDomainId } from "@/features/settings-panel/domainSettingsHelpers";

function ThemeWrap({
  theme,
  children,
}: {
  theme: "zai-dark" | "zai-light";
  children: ReactNode;
}) {
  return <div data-theme={theme}>{children}</div>;
}

function OneOpenHarness() {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const rows = [
    { id: "synth-alpha", name: "Synthetic Alpha Domain" },
    { id: "synth-beta", name: "Synthetic Beta Domain" },
  ];
  return (
    <ThemeWrap theme="zai-dark">
      {rows.map((row) => {
        const expanded = expandedId === row.id;
        const panelId = `knowledge-domain-${row.id}-panel`;
        return (
          <DomainAccordionRow
            key={row.id}
            displayName={row.name}
            domainId={row.id}
            expanded={expanded}
            panelId={panelId}
            stateLabel="Running"
            stateTone="good"
            onToggleExpand={() => setExpandedId((current) => nextExpandedDomainId(current, row.id))}
            lifecycleControl={
              <ToggleSwitch
                checked={false}
                aria-label={`Start ${row.name}`}
                onCheckedChange={() => undefined}
              />
            }
          >
            <p>Query eligible</p>
            <p>Runtime ready</p>
            <p>embed-synth · 768d · locked</p>
          </DomainAccordionRow>
        );
      })}
    </ThemeWrap>
  );
}

describe("Domains accordion parity (R10)", () => {
  it("renders collapsed identity and state", () => {
    render(
      <ThemeWrap theme="zai-light">
        <DomainAccordionRow
          displayName="Synthetic Alpha Domain"
          domainId="synth-alpha"
          expanded={false}
          panelId="knowledge-domain-synth-alpha-panel"
          stateLabel="Running"
          stateTone="good"
          onToggleExpand={() => undefined}
          lifecycleControl={<span>lifecycle</span>}
        />
      </ThemeWrap>,
    );
    expect(screen.getByText("Synthetic Alpha Domain")).toBeInTheDocument();
    expect(screen.getByText("synth-alpha")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
    const expand = screen.getByRole("button", { name: "Expand Synthetic Alpha Domain" });
    expect(expand).toHaveAttribute("aria-expanded", "false");
    expect(expand).toHaveAttribute("aria-controls", "knowledge-domain-synth-alpha-panel");
    expect(screen.queryByRole("region", { name: "Synthetic Alpha Domain details" })).not.toBeInTheDocument();
  });

  it("keeps the expand control keyboard-focusable and opens locked-fact region", async () => {
    const user = userEvent.setup();
    function Expandable() {
      const [expanded, setExpanded] = useState(false);
      return (
        <ThemeWrap theme="zai-dark">
          <DomainAccordionRow
            displayName="Synthetic Alpha Domain"
            domainId="synth-alpha"
            expanded={expanded}
            panelId="knowledge-domain-synth-alpha-panel"
            stateLabel="Running"
            stateTone="good"
            onToggleExpand={() => setExpanded((value) => !value)}
            lifecycleControl={
              <ToggleSwitch
                checked
                aria-label="Stop Synthetic Alpha Domain"
                onCheckedChange={() => undefined}
              />
            }
          >
            <p>Query eligible</p>
            <p>Runtime ready</p>
            <p>embed-synth · 768d · locked</p>
          </DomainAccordionRow>
        </ThemeWrap>
      );
    }
    render(<Expandable />);
    const control = screen.getByRole("button", { name: "Expand Synthetic Alpha Domain" });
    control.focus();
    expect(control).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("button", { name: "Collapse Synthetic Alpha Domain" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    const region = screen.getByRole("region", { name: "Synthetic Alpha Domain details" });
    expect(within(region).getByText("Query eligible")).toBeInTheDocument();
    expect(within(region).getByText("embed-synth · 768d · locked")).toBeInTheDocument();
  });

  it("keeps one-open disclosure when opening another row", async () => {
    const user = userEvent.setup();
    render(<OneOpenHarness />);
    await user.click(screen.getByRole("button", { name: "Expand Synthetic Alpha Domain" }));
    expect(screen.getByRole("region", { name: "Synthetic Alpha Domain details" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Expand Synthetic Beta Domain" }));
    expect(screen.queryByRole("region", { name: "Synthetic Alpha Domain details" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Synthetic Beta Domain details" })).toBeInTheDocument();
  });
});
