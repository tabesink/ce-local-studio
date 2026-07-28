import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SegmentedControl } from "@/_shared/ui";

const ITEMS = [
  { id: "compact", label: "Compact" },
  { id: "comfortable", label: "Comfortable" },
] as const;

describe("SegmentedControl parity (R10)", () => {
  it("exposes one selected tab in a tablist", () => {
    render(<SegmentedControl items={[...ITEMS]} value="compact" onChange={() => undefined} />);
    expect(screen.getByRole("tablist")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Compact" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Comfortable" })).toHaveAttribute("aria-selected", "false");
  });

  it("emits selection intent from a segment button", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<SegmentedControl items={[...ITEMS]} value="compact" onChange={onChange} size="sm" />);
    await user.click(screen.getByRole("tab", { name: "Comfortable" }));
    expect(onChange).toHaveBeenCalledWith("comfortable");
  });

  it("renders within the light theme region", () => {
    render(<div data-theme="zai-light"><SegmentedControl items={[...ITEMS]} value="comfortable" onChange={() => undefined} /></div>);
    expect(screen.getByRole("tablist").parentElement).toHaveAttribute("data-theme", "zai-light");
  });
});
