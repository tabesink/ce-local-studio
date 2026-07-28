import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

type Row = { key: string; label: string; status: string };

function ResourceTableHarness({
  rows,
  selectedKey,
  onSelect,
}: {
  rows: Row[];
  selectedKey: string | null;
  onSelect: (key: string) => void;
}) {
  return (
    <div data-theme="zai-dark" style={{ overflowX: "auto" }}>
      <table>
        <caption>Synthetic resources</caption>
        <thead><tr><th>Resource</th><th>Status</th></tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key}>
              <td>
                <button
                  type="button"
                  aria-pressed={selectedKey === row.key}
                  onClick={() => onSelect(row.key)}
                >
                  {row.label}
                </button>
              </td>
              <td>{row.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const ROWS = [
  { key: "sample-a", label: "Sample handbook", status: "Available" },
  { key: "sample-b", label: "Example checklist", status: "Draft" },
];

describe("ResourceTable parity (R10)", () => {
  it("exposes a caption, columns, visible statuses, and selected row", () => {
    render(<ResourceTableHarness rows={ROWS} selectedKey="sample-a" onSelect={() => undefined} />);
    expect(screen.getByRole("table", { name: "Synthetic resources" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Resource" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sample handbook" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Draft")).toBeInTheDocument();
  });

  it("activates a row with the keyboard", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<ResourceTableHarness rows={ROWS} selectedKey={null} onSelect={onSelect} />);
    const row = screen.getByRole("button", { name: "Example checklist" });
    row.focus();
    await user.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledWith("sample-b");
  });
});
