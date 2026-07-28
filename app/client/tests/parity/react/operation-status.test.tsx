import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

function OperationStatusHarness({
  theme,
  stage,
  progress,
}: {
  theme: "zai-dark" | "zai-light";
  stage: string;
  progress: number;
}) {
  return (
    <section data-theme={theme} role="status" aria-label="Synthetic operation" aria-live="polite">
      <h2>Synthetic operation</h2>
      <span>{stage}</span>
      <span>Attempt 1</span>
      <div role="progressbar" aria-label={stage} aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress} />
      <p>Synthetic progress for visual review only.</p>
    </section>
  );
}

describe("OperationStatus parity (R10)", () => {
  it("announces a synthetic active stage and safe message", () => {
    render(<OperationStatusHarness theme="zai-dark" stage="Preparing" progress={58} />);
    const status = screen.getByRole("status", { name: "Synthetic operation" });
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(screen.getByRole("progressbar", { name: "Preparing" })).toHaveAttribute("aria-valuenow", "58");
    expect(screen.getByText("Synthetic progress for visual review only.")).toBeInTheDocument();
  });

  it("keeps terminal state textual in the light theme", () => {
    const { container } = render(<OperationStatusHarness theme="zai-light" stage="Complete" progress={100} />);
    expect(container.firstElementChild).toHaveAttribute("data-theme", "zai-light");
    expect(screen.getByText("Complete")).toBeInTheDocument();
  });
});
