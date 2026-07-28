import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

function SourceOperationPanelHarness({ theme }: { theme: "zai-dark" | "zai-light" }) {
  return (
    <section data-theme={theme} role="region" aria-label="Source operation">
      <p>Source operation</p>
      <h2>Synthetic handbook</h2>
      <dl>
        <div><dt>Preparation</dt><dd>Preparing</dd></div>
        <div><dt>Index</dt><dd>Waiting</dd></div>
      </dl>
    </section>
  );
}

describe("SourceOperationPanel parity (R10)", () => {
  it("exposes only synthetic ordered lifecycle labels", () => {
    render(<SourceOperationPanelHarness theme="zai-dark" />);
    const panel = screen.getByRole("region", { name: "Source operation" });
    expect(within(panel).getByRole("heading", { name: "Synthetic handbook" })).toBeInTheDocument();
    expect(within(panel).getByText("Preparation")).toBeInTheDocument();
    expect(within(panel).getByText("Preparing")).toBeInTheDocument();
    expect(within(panel).getByText("Index")).toBeInTheDocument();
    expect(within(panel).getByText("Waiting")).toBeInTheDocument();
    expect(within(panel).queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders the same lifecycle geometry in the light theme", () => {
    const { container } = render(<SourceOperationPanelHarness theme="zai-light" />);
    expect(container.firstElementChild).toHaveAttribute("data-theme", "zai-light");
  });
});
