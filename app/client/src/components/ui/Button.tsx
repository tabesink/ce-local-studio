"use client";

import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cx } from "@/lib/cx";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost" | "icon";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  loading?: boolean;
  children?: ReactNode;
}

const variants: Record<ButtonVariant, string> = {
  primary: "bg-[var(--ui-fg)] text-[var(--ui-bg)] hover:opacity-90",
  secondary: "border border-[var(--ui-border)] text-[var(--dim)] hover:bg-[var(--ui-hover)] hover:text-[var(--fg)]",
  danger: "text-[var(--ui-danger)] hover:bg-[color-mix(in_srgb,var(--ui-danger)_14%,transparent)]",
  ghost: "text-[var(--dim)] hover:bg-[var(--ui-hover)] hover:text-[var(--fg)]",
  icon: "size-7 text-[var(--dim)] hover:bg-[var(--ui-hover)] hover:text-[var(--fg)]",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", loading = false, children, className, disabled, type = "button", ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      className={cx(
        "inline-flex h-7 items-center justify-center gap-2 rounded-[var(--rad-lg)] px-3 text-[length:var(--fs-md)] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--ring)]",
        variants[variant],
        className,
      )}
      {...props}
    >
      {loading ? <span aria-hidden className="size-3 rounded-full border border-current border-t-transparent" /> : null}
      {children}
    </button>
  );
});
