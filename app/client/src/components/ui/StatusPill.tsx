import type { ReactNode } from "react";
import { cx } from "@/lib/cx";

/* Local Studio status grammar — ported from
   .reference-LS-frontend/templates/nextjs-feature-demos/_shared/ui (StatusDot, StatusPill).
   Status always pairs a dot/badge with text; never color alone. */

export type UiTone = "default" | "good" | "warning" | "danger" | "info";
export type StatusPillVariant = "dot" | "badge";

const dotClasses: Record<UiTone, string> = {
  default: "bg-[var(--ui-muted)]",
  good: "bg-[var(--ui-success)]",
  warning: "bg-[var(--ui-warning)]",
  danger: "bg-[var(--ui-danger)]",
  info: "bg-[var(--ui-info)]",
};

const textClasses: Record<UiTone, string> = {
  default: "text-[var(--ui-muted)]",
  good: "text-[var(--ui-success)]",
  warning: "text-[var(--ui-warning)]",
  danger: "text-[var(--ui-danger)]",
  info: "text-[var(--ui-info)]",
};

const badgeClasses: Record<UiTone, string> = {
  default: "bg-[var(--ui-surface)] text-[var(--ui-muted)]",
  good: "bg-[color-mix(in_srgb,var(--ui-success)_10%,transparent)] text-[var(--ui-success)]",
  warning: "bg-[color-mix(in_srgb,var(--ui-warning)_10%,transparent)] text-[var(--ui-warning)]",
  danger: "bg-[color-mix(in_srgb,var(--ui-danger)_10%,transparent)] text-[var(--ui-danger)]",
  info: "bg-[color-mix(in_srgb,var(--ui-info)_10%,transparent)] text-[var(--ui-info)]",
};

export function StatusDot({ tone = "default", className }: { tone?: UiTone; className?: string }) {
  return <span aria-hidden className={cx("h-[5px] w-[5px] rounded-full", dotClasses[tone], className)} />;
}

export function StatusPill({
  tone = "default",
  variant = "dot",
  children,
  className,
}: {
  tone?: UiTone;
  variant?: StatusPillVariant;
  children: ReactNode;
  className?: string;
}) {
  if (variant === "badge") {
    return (
      <span
        className={cx(
          "inline-flex h-5 items-center rounded-[var(--rad-xs)] px-1.5 text-[length:var(--fs-xs)] font-medium",
          badgeClasses[tone],
          className,
        )}
      >
        {children}
      </span>
    );
  }

  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 text-[length:var(--fs-sm)] font-normal",
        textClasses[tone],
        className,
      )}
    >
      <StatusDot tone={tone} />
      {children}
    </span>
  );
}
