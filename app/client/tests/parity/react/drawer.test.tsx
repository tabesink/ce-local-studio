import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Drawer, DrawerBody, DrawerFooter, DrawerHeader } from "@/_shared/ui";

function ExampleDrawer({ onClose = () => undefined }: { onClose?: () => void }) {
  return (
    <Drawer width={440}>
      <DrawerHeader title="Details" onClose={onClose} />
      <DrawerBody>Synthetic drawer content</DrawerBody>
      <DrawerFooter status="Saved"><button>Done</button></DrawerFooter>
    </Drawer>
  );
}

describe("Drawer parity (R10)", () => {
  it("renders aside chrome with header, body, and footer content", () => {
    render(<ExampleDrawer />);
    expect(screen.getByRole("complementary")).toHaveStyle({ width: "440px" });
    expect(screen.getByText("Synthetic drawer content")).toBeInTheDocument();
    expect(screen.getByText("Saved")).toBeInTheDocument();
  });

  it("emits close intent from the named close button", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<ExampleDrawer onClose={onClose} />);
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("renders within the light theme region", () => {
    render(<div data-theme="zai-light"><ExampleDrawer /></div>);
    expect(screen.getByRole("complementary").closest("[data-theme]")).toHaveAttribute("data-theme", "zai-light");
  });
});
