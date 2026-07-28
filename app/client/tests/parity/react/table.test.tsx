import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Table, TBody, TCell, TH, THead, TRow } from "@/_shared/ui";

function ExampleTable({ onRowClick }: { onRowClick?: () => void }) {
  return (
    <Table>
      <THead><TRow><TH>Item</TH><TH>State</TH></TRow></THead>
      <TBody><TRow onClick={onRowClick}><TCell>Example one</TCell><TCell>Ready</TCell></TRow></TBody>
    </Table>
  );
}

describe("Table parity (R10)", () => {
  it("preserves native table semantics", () => {
    render(<ExampleTable />);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Item" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Ready" })).toBeInTheDocument();
  });

  it("emits row click intent when supplied", async () => {
    const user = userEvent.setup();
    const onRowClick = vi.fn();
    render(<ExampleTable onRowClick={onRowClick} />);
    await user.click(screen.getByRole("cell", { name: "Example one" }));
    expect(onRowClick).toHaveBeenCalledTimes(1);
  });

  it("supports a borderless wrapper in a light theme", () => {
    render(<div data-theme="zai-light"><Table bordered={false}><TBody><TRow><TCell>Example</TCell></TRow></TBody></Table></div>);
    expect(screen.getByRole("table").parentElement).not.toHaveClass("border");
  });
});
