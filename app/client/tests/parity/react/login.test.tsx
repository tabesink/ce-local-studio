import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginPage } from "@/features/auth/LoginPage";

const replace = vi.fn();
const login = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
}));

vi.mock("@/features/auth/auth-store", () => ({
  useAuthStore: (selector: (state: unknown) => unknown) =>
    selector({
      login,
    }),
}));

function ThemeWrap({
  theme,
  children,
}: {
  theme: "zai-dark" | "zai-light";
  children: ReactNode;
}) {
  return <div data-theme={theme}>{children}</div>;
}

describe("Login parity (R10)", () => {
  beforeEach(() => {
    replace.mockReset();
    login.mockReset();
    login.mockResolvedValue(undefined);
  });

  it("renders centered credential card", () => {
    render(
      <ThemeWrap theme="zai-dark">
        <LoginPage />
      </ThemeWrap>,
    );
    expect(screen.getByRole("heading", { name: "Context Engine" })).toBeInTheDocument();
    expect(screen.getByText("Sign in with your team account.")).toBeInTheDocument();
    expect(screen.getByLabelText("Username")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("keeps username, password, and submit in keyboard tab order", async () => {
    const user = userEvent.setup();
    render(
      <ThemeWrap theme="zai-light">
        <LoginPage />
      </ThemeWrap>,
    );
    const username = screen.getByLabelText("Username");
    const password = screen.getByLabelText("Password");
    const submit = screen.getByRole("button", { name: "Sign in" });
    username.focus();
    expect(username).toHaveFocus();
    await user.tab();
    expect(password).toHaveFocus();
    await user.tab();
    expect(submit).toHaveFocus();
  });

  it("submits credentials through auth store without network", async () => {
    const user = userEvent.setup();
    render(
      <ThemeWrap theme="zai-dark">
        <LoginPage />
      </ThemeWrap>,
    );
    await user.type(screen.getByLabelText("Username"), " synth-user ");
    await user.type(screen.getByLabelText("Password"), "synth-pass");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(login).toHaveBeenCalledWith("synth-user", "synth-pass");
    expect(replace).toHaveBeenCalledWith("/chat");
  });
});
