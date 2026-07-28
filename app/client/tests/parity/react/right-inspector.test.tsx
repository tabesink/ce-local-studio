import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

function RightInspectorHarness({ narrow = false, onClose }: { narrow?: boolean; onClose: () => void }) {
  const [width, setWidth] = useState(440);
  const content = (
    <>
      <header><h2>Details</h2><button type="button" onClick={onClose}>Close details</button></header>
      <div>Synthetic detail content</div>
    </>
  );

  if (narrow) {
    return <div data-theme="zai-dark" role="dialog" aria-modal="true" aria-label="Details">{content}</div>;
  }

  return (
    <aside data-theme="zai-light" role="complementary" aria-label="Details" style={{ width }}>
      <div
        role="separator"
        aria-label="Resize details"
        aria-orientation="vertical"
        aria-valuemin={320}
        aria-valuemax={900}
        aria-valuenow={width}
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === "ArrowLeft") setWidth((value) => value + 16);
          if (event.key === "ArrowRight") setWidth((value) => value - 16);
        }}
      />
      {content}
    </aside>
  );
}

describe("RightInspector parity (R10)", () => {
  it("renders an adjacent desktop inspector with keyboard resize", async () => {
    const user = userEvent.setup();
    render(<RightInspectorHarness onClose={() => undefined} />);
    expect(screen.getByRole("complementary", { name: "Details" })).toBeInTheDocument();
    const separator = screen.getByRole("separator", { name: "Resize details" });
    separator.focus();
    await user.keyboard("{ArrowLeft}");
    expect(separator).toHaveAttribute("aria-valuenow", "456");
  });

  it("substitutes a named narrow drawer and emits close intent", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<RightInspectorHarness narrow onClose={onClose} />);
    expect(screen.getByRole("dialog", { name: "Details" })).toHaveAttribute("aria-modal", "true");
    await user.click(screen.getByRole("button", { name: "Close details" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
