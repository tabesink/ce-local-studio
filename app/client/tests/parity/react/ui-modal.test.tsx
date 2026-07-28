import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { UiModal, UiModalHeader } from "@/_shared/ui";

function ThemeWrap({
  theme,
  children,
}: {
  theme: "zai-dark" | "zai-light";
  children: ReactNode;
}) {
  return <div data-theme={theme}>{children}</div>;
}

describe("UiModal parity (R10)", () => {
  it("renders nothing when closed", () => {
    render(
      <UiModal isOpen={false} onClose={() => undefined}>
        <UiModalHeader title="Confirm action" onClose={() => undefined} />
      </UiModal>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens dialog with titled header when isOpen", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <UiModal isOpen onClose={() => undefined}>
          <UiModalHeader title="Confirm action" onClose={() => undefined} />
          <div>This synthetic action cannot be undone.</div>
        </UiModal>
      </ThemeWrap>,
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(within(dialog).getByRole("heading", { name: "Confirm action" })).toBeInTheDocument();
    expect(screen.getByText("This synthetic action cannot be undone.")).toBeInTheDocument();
  });

  it("closes via header Close control", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <ThemeWrap theme="zai-light">
        <UiModal isOpen onClose={onClose}>
          <UiModalHeader title="Confirm action" onClose={onClose} />
        </UiModal>
      </ThemeWrap>,
    );
    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("header Close is keyboard activatable", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <UiModal isOpen onClose={onClose}>
        <UiModalHeader title="Confirm action" onClose={onClose} />
      </UiModal>,
    );
    const closeButton = within(screen.getByRole("dialog")).getByRole("button", { name: "Close" });
    closeButton.focus();
    expect(closeButton).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
