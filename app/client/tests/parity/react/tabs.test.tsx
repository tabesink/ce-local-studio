import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Tabs } from "@/_shared/ui";

const ITEMS = [
  { id: "overview", label: "Overview" },
  { id: "details", label: "Details" },
] as const;

describe("Tabs parity (R10)", () => {
  it.each(["underline", "pill", "button-group"] as const)("renders the %s variant labels", (variant) => {
    render(<Tabs variant={variant} items={[...ITEMS]} activeTab="overview" onSelectTab={() => undefined} />);
    expect(screen.getByRole("button", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Details" })).toBeInTheDocument();
  });

  it("emits selection intent from a native button", async () => {
    const user = userEvent.setup();
    const onSelectTab = vi.fn();
    render(<Tabs items={[...ITEMS]} activeTab="overview" onSelectTab={onSelectTab} />);
    await user.click(screen.getByRole("button", { name: "Details" }));
    expect(onSelectTab).toHaveBeenCalledWith("details");
  });

  it("renders within the light theme region", () => {
    render(<div data-theme="zai-light"><Tabs variant="pill" items={[...ITEMS]} activeTab="details" onSelectTab={() => undefined} /></div>);
    expect(screen.getByRole("button", { name: "Details" }).closest("[data-theme]")).toHaveAttribute("data-theme", "zai-light");
  });
});
