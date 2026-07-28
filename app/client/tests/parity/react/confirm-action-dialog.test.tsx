import { useEffect, useRef } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { UiModal, UiModalHeader } from "@/_shared/ui";

function ConfirmActionDialogHarness({
  open,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (open) cancelRef.current?.focus();
  }, [open]);

  return (
    <div data-theme="zai-dark">
      <UiModal isOpen={open} onClose={onCancel} maxWidth="max-w-md">
        <UiModalHeader title="Remove synthetic item?" onClose={onCancel} />
        <div>
          <strong>Sample handbook</strong>
          <p>This removes the item from this synthetic view.</p>
          <button ref={cancelRef} type="button" onClick={onCancel}>Cancel</button>
          <button type="button" onClick={onConfirm}>Remove</button>
        </div>
      </UiModal>
    </div>
  );
}

describe("ConfirmActionDialog parity (R10)", () => {
  it("uses the titled UiModal shell and initially focuses Cancel", () => {
    render(<ConfirmActionDialogHarness open onCancel={() => undefined} onConfirm={() => undefined} />);
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
    expect(screen.getByRole("heading", { name: "Remove synthetic item?" })).toBeInTheDocument();
    expect(screen.getByText("Sample handbook")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
  });

  it("requires an explicit confirmation activation", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<ConfirmActionDialogHarness open onCancel={vi.fn()} onConfirm={onConfirm} />);
    expect(onConfirm).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Remove" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
