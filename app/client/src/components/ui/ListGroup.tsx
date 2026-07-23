"use client";

import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cx } from "@/lib/cx";

/* Local Studio dense list grammar — ported from
   .reference-LS-frontend/templates/nextjs-feature-demos/_shared/ui
   (ListGroup, ListRow, RowValue, EmptySafeNotice). */

export function ListGroup({
  title,
  description,
  actions,
  children,
  className,
  collapsible = false,
  defaultOpen = true,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  collapsible?: boolean;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const showBody = collapsible ? open : true;
  return (
    <section className={cx("mb-6 last:mb-0", className)}>
      {title || actions ? (
        <div className="mb-1.5 flex items-end justify-between gap-3 px-3.5">
          {collapsible ? (
            <button
              type="button"
              onClick={() => setOpen((value) => !value)}
              aria-expanded={open}
              className="group flex items-center gap-1.5 text-[var(--ui-muted)] hover:text-[var(--ui-fg)]"
            >
              <ChevronDown
                className={cx("h-3 w-3 transition-transform", open ? "" : "-rotate-90")}
                aria-hidden
              />
              <h3 className="text-[length:var(--fs-md)] font-semibold tracking-[-0.005em]">{title}</h3>
            </button>
          ) : (
            <h3 className="text-[length:var(--fs-md)] font-semibold tracking-[-0.005em] text-[var(--ui-muted)]">
              {title}
            </h3>
          )}
          {actions ? <div className="shrink-0">{actions}</div> : null}
        </div>
      ) : null}
      {showBody ? (
        <div className="overflow-hidden rounded-md border border-[var(--ui-border)] bg-[var(--ui-surface)] shadow-[0_1px_0_rgba(255,255,255,0.025)_inset] [&>*+*]:before:pointer-events-none [&>*+*]:before:absolute [&>*+*]:before:left-0 [&>*+*]:before:right-0 [&>*+*]:before:top-0 [&>*+*]:before:h-px [&>*+*]:before:bg-[var(--ui-separator)] [&>*]:relative">
          {children}
        </div>
      ) : null}
      {description && showBody ? (
        <p className="mt-1.5 px-3.5 text-[length:var(--fs-sm)] leading-relaxed text-[var(--ui-muted)]">
          {description}
        </p>
      ) : null}
    </section>
  );
}

export function ListRow({
  label,
  description,
  value,
  control,
  status,
  actions,
  children,
  className,
  variant = "settings",
}: {
  label: string;
  description?: ReactNode;
  value?: ReactNode;
  control?: ReactNode;
  status?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
  variant?: "settings" | "resource";
}) {
  const primaryValue = control ?? value;

  if (variant === "resource") {
    return (
      <div
        className={cx(
          "px-3.5 py-3 transition-colors hover:bg-[color-mix(in_srgb,var(--ui-hover)_35%,transparent)]",
          className,
        )}
      >
        <div className="grid min-w-0 grid-cols-1 gap-2.5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
          <div className="min-w-0 space-y-1">
            <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
              <div
                className="min-w-0 break-words text-[length:var(--fs-base)] font-medium leading-snug text-[var(--ui-fg)]"
                title={label}
              >
                {label}
              </div>
            </div>
            {description ? (
              <div className="line-clamp-2 text-[length:var(--fs-sm)] leading-relaxed text-[var(--ui-muted)]">
                {description}
              </div>
            ) : null}
          </div>
          {status || actions ? (
            <div className="flex min-w-0 flex-wrap items-center gap-1.5 sm:justify-end sm:pt-0.5">
              {status ? <div className="shrink-0">{status}</div> : null}
              {actions ? <div className="flex shrink-0 items-center gap-1.5">{actions}</div> : null}
            </div>
          ) : null}
        </div>
        {primaryValue ? <div className="mt-2 min-w-0 text-[var(--ui-muted)]">{primaryValue}</div> : null}
        {children ? (
          <div className="mt-2 min-w-0 space-y-1.5 border-t border-[color-mix(in_srgb,var(--ui-separator)_70%,transparent)] pt-2 text-[length:var(--fs-sm)] leading-relaxed">
            {children}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div
      className={cx(
        "px-3.5 py-2.5 transition-colors hover:bg-[color-mix(in_srgb,var(--ui-hover)_35%,transparent)]",
        className,
      )}
    >
      {/* Shared 2-column grid pins a fixed label column so controls align
          vertically across rows; expanded children indent to the control column. */}
      <div className="grid min-h-7 grid-cols-1 gap-1.5 md:grid-cols-[minmax(160px,0.42fr)_minmax(0,1fr)] md:items-center md:gap-5">
        <div className="min-w-0">
          <div className="truncate text-[length:var(--fs-base)] font-medium text-[var(--ui-fg)]" title={label}>
            {label}
          </div>
          {description ? (
            <div className="mt-0.5 text-[length:var(--fs-sm)] leading-relaxed text-[var(--ui-muted)]">
              {description}
            </div>
          ) : null}
        </div>
        <div className="flex min-w-0 items-center justify-end gap-2">
          {control ?? value ?? null}
          {status ? <div className="shrink-0">{status}</div> : null}
          {actions ? <div className="flex shrink-0 items-center gap-1.5">{actions}</div> : null}
        </div>
      </div>
      {children ? (
        <div className="mt-2 grid grid-cols-1 gap-1.5 md:grid-cols-[minmax(160px,0.42fr)_minmax(0,1fr)] md:gap-5">
          <div className="hidden md:block" />
          <div className="min-w-0">{children}</div>
        </div>
      ) : null}
    </div>
  );
}

export function RowValue({
  children,
  mono = false,
  dim = false,
  truncate = false,
  wrap = false,
  className,
}: {
  children: ReactNode;
  mono?: boolean;
  dim?: boolean;
  truncate?: boolean;
  wrap?: boolean;
  className?: string;
}) {
  const value = children === null || children === undefined || children === "" ? "Not set" : children;
  return (
    <div
      className={cx(
        "text-[length:var(--fs-base)]",
        mono ? "font-mono text-[length:var(--fs-md)]" : "",
        dim ? "text-[var(--ui-muted)]" : "text-[color-mix(in_srgb,var(--ui-fg)_80%,transparent)]",
        truncate ? "min-w-0 truncate" : "",
        wrap && !truncate ? "min-w-0 whitespace-normal break-words [overflow-wrap:anywhere]" : "",
        className,
      )}
      title={typeof children === "string" ? children : undefined}
    >
      {value}
    </div>
  );
}

export function EmptySafeNotice({ children }: { children: ReactNode }) {
  return (
    <div className="px-3.5 py-2.5 text-[length:var(--fs-md)] leading-relaxed text-[var(--ui-muted)]">
      {children}
    </div>
  );
}
