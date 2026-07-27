import { existsSync } from "node:fs";
import path from "node:path";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button, type ButtonVariant } from "@/ui";

const PARITY_ROOT = path.resolve(__dirname, "..");

function ThemeWrap({
  theme,
  children,
}: {
  theme: "zai-dark" | "zai-light";
  children: ReactNode;
}) {
  return <div data-theme={theme}>{children}</div>;
}

describe("Button parity (R10)", () => {
  it("asserts starter manifests exist and accordion parity files do not", () => {
    for (const name of ["button", "input", "status-pill", "settings-row"]) {
      expect(existsSync(path.join(PARITY_ROOT, "manifests", `${name}.json`))).toBe(true);
      expect(existsSync(path.join(PARITY_ROOT, "fixtures", `${name}.html`))).toBe(true);
      expect(existsSync(path.join(PARITY_ROOT, "react", `${name}.test.tsx`))).toBe(true);
    }
    for (const forbidden of [
      "domains-accordion",
      "domain-accordion",
      "accordion",
      "domains_accordion",
    ]) {
      expect(existsSync(path.join(PARITY_ROOT, "manifests", `${forbidden}.json`))).toBe(false);
      expect(existsSync(path.join(PARITY_ROOT, "fixtures", `${forbidden}.html`))).toBe(false);
      expect(existsSync(path.join(PARITY_ROOT, "react", `${forbidden}.test.tsx`))).toBe(false);
    }
  });

  it("renders each variant with its synthetic label", () => {
    const variants: Array<{ variant: ButtonVariant; label: string }> = [
      { variant: "primary", label: "Save draft" },
      { variant: "secondary", label: "Cancel" },
      { variant: "danger", label: "Remove item" },
      { variant: "ghost", label: "More options" },
      { variant: "icon", label: "Open menu" },
    ];
    render(
      <ThemeWrap theme="zai-dark">
        {variants.map(({ variant, label }) => (
          <Button key={variant} variant={variant}>
            {label}
          </Button>
        ))}
      </ThemeWrap>,
    );
    for (const { label } of variants) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
  });

  it("sets disabled and aria-busy while loading and retains the label", () => {
    render(
      <ThemeWrap theme="zai-light">
        <Button loading>Saving</Button>
      </ThemeWrap>,
    );
    const button = screen.getByRole("button", { name: /Saving/i });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toHaveTextContent("Saving");
  });

  it("honors native disabled", () => {
    render(<Button disabled>Save draft</Button>);
    expect(screen.getByRole("button", { name: "Save draft" })).toBeDisabled();
  });

  it("activates on Enter and Space via keyboard", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Save draft</Button>);
    const button = screen.getByRole("button", { name: "Save draft" });
    button.focus();
    expect(button).toHaveFocus();
    await user.keyboard("{Enter}");
    await user.keyboard(" ");
    expect(onClick).toHaveBeenCalledTimes(2);
  });

  it("respects prefers-reduced-motion media without dropping the label", () => {
    const matchMedia = window.matchMedia;
    window.matchMedia = ((query: string) =>
      ({
        matches: query.includes("prefers-reduced-motion"),
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      })) as typeof window.matchMedia;

    try {
      render(
        <ThemeWrap theme="zai-dark">
          <Button loading>Saving</Button>
        </ThemeWrap>,
      );
      expect(screen.getByRole("button", { name: /Saving/i })).toHaveTextContent("Saving");
    } finally {
      window.matchMedia = matchMedia;
    }
  });
});
