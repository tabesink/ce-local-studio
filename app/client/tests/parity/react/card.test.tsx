import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Card } from "@/_shared/ui";

describe("Card parity (R10)", () => {
  it.each([
    ["sm", "p-3"],
    ["md", "p-4"],
    ["lg", "p-6"],
  ] as const)("applies %s padding", (padding, expectedClass) => {
    render(<Card padding={padding}><h2>Synthetic card</h2></Card>);
    expect(screen.getByRole("heading", { name: "Synthetic card" }).parentElement).toHaveClass(expectedClass);
  });

  it("can omit its border without changing child semantics", () => {
    render(<Card bordered={false}><p>Compact supporting text</p></Card>);
    const card = screen.getByText("Compact supporting text").parentElement;
    expect(card).not.toHaveClass("border");
  });

  it("renders within a light theme region", () => {
    render(<div data-theme="zai-light"><Card>Synthetic card</Card></div>);
    expect(screen.getByText("Synthetic card").closest("[data-theme]")).toHaveAttribute("data-theme", "zai-light");
  });
});
