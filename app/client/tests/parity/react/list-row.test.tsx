import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ListRow } from "@/_shared/ui";

describe("ListRow parity (R10)", () => {
  it("renders the settings label, description, and value", () => {
    render(<ListRow label="Display density" description="Choose a compact presentation" value="Compact" />);
    expect(screen.getByText("Display density")).toBeInTheDocument();
    expect(screen.getByText("Choose a compact presentation")).toBeInTheDocument();
    expect(screen.getByText("Compact")).toBeInTheDocument();
  });

  it("keeps an embedded action independently operable", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<ListRow label="Example resource" variant="resource" actions={<button onClick={onClick}>Open</button>} />);
    await user.click(screen.getByRole("button", { name: "Open" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("renders status and expanded content in the light theme", () => {
    render(<div data-theme="zai-light"><ListRow label="Example resource" status="Ready">Synthetic detail</ListRow></div>);
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("Synthetic detail")).toBeInTheDocument();
  });
});
