import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorBox } from "@/components/ui/ErrorBox";

function ThemeWrap({
  theme,
  children,
}: {
  theme: "zai-dark" | "zai-light";
  children: ReactNode;
}) {
  return <div data-theme={theme}>{children}</div>;
}

const MESSAGE = "Sign-in failed. Check your credentials and try again.";

describe("ErrorBox parity (R10)", () => {
  it("renders message with role=alert", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <ErrorBox message={MESSAGE} />
      </ThemeWrap>,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(MESSAGE);
  });

  it("retains message under zai-light theme wrapper", () => {
    render(
      <ThemeWrap theme="zai-light">
        <ErrorBox message={MESSAGE} />
      </ThemeWrap>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(MESSAGE);
  });

  it("accepts optional className without dropping the message", () => {
    render(<ErrorBox className="mt-4" message={MESSAGE} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveClass("mt-4");
    expect(alert).toHaveTextContent(MESSAGE);
  });
});
