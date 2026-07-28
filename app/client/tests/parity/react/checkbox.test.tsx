import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Checkbox } from "@/_shared/ui";

describe("Checkbox parity (R10)", () => {
  it("uses its visible label as the accessible name", () => {
    render(<Checkbox checked={false} onChange={() => undefined} label="Include summaries" />);
    expect(screen.getByRole("checkbox", { name: "Include summaries" })).not.toBeChecked();
  });

  it("emits the next checked value from the label-owned hit area", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Checkbox checked={false} onChange={onChange} label="Include summaries" />);
    await user.click(screen.getByText("Include summaries"));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("exposes controlled checked state in the light theme", () => {
    render(<div data-theme="zai-light"><Checkbox checked onChange={() => undefined} label="Include citations" /></div>);
    expect(screen.getByRole("checkbox", { name: "Include citations" })).toBeChecked();
  });
});
