import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Textarea } from "@/_shared/ui";

describe("Textarea parity (R10)", () => {
  it("passes native naming, rows, and value behavior through", async () => {
    const user = userEvent.setup();
    render(<Textarea aria-label="Summary" rows={3} placeholder="Add a short summary" />);
    const textarea = screen.getByRole("textbox", { name: "Summary" });
    await user.type(textarea, "Synthetic note");
    expect(textarea).toHaveValue("Synthetic note");
    expect(textarea).toHaveAttribute("rows", "3");
  });

  it("supports native disabled state", () => {
    render(<Textarea aria-label="Summary" disabled defaultValue="Synthetic note" />);
    expect(screen.getByRole("textbox", { name: "Summary" })).toBeDisabled();
  });

  it("renders inside the light theme region", () => {
    render(<div data-theme="zai-light"><Textarea aria-label="Light summary" /></div>);
    expect(screen.getByRole("textbox", { name: "Light summary" }).parentElement).toHaveAttribute("data-theme", "zai-light");
  });
});
