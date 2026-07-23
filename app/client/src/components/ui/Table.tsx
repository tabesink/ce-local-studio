import type { ReactNode, TdHTMLAttributes, ThHTMLAttributes } from "react";
import { cx } from "@/lib/cx";

/* Local Studio table grammar — ported from
   .reference-LS-frontend/templates/nextjs-feature-demos/_shared/ui
   (Table, THead, TBody, TRow, TH, TCell). */

export function Table({
  children,
  className = "",
  tableClassName = "",
  bordered = true,
}: {
  children: ReactNode;
  className?: string;
  tableClassName?: string;
  bordered?: boolean;
}) {
  return (
    <div
      className={cx(
        "overflow-x-auto",
        bordered ? "overflow-hidden rounded-[var(--ui-radius)] border border-[var(--ui-border)]" : "",
        className,
      )}
    >
      <table className={cx("w-full text-left", tableClassName)}>{children}</table>
    </div>
  );
}

export function THead({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <thead className={cx("border-b border-[var(--ui-border)] bg-[var(--ui-surface)]", className)}>
      {children}
    </thead>
  );
}

export function TBody({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <tbody className={cx("divide-y divide-[var(--ui-border)]", className)}>{children}</tbody>;
}

export function TRow({
  children,
  className = "",
  onClick,
  interactive,
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  interactive?: boolean;
}) {
  return (
    <tr
      className={cx(
        "transition-colors",
        interactive || onClick
          ? "cursor-pointer hover:bg-[var(--ui-hover)]"
          : "hover:bg-[color-mix(in_srgb,var(--ui-surface)_50%,transparent)]",
        className,
      )}
      onClick={onClick}
    >
      {children}
    </tr>
  );
}

export function TH({
  children,
  align = "left",
  className = "",
  ...props
}: ThHTMLAttributes<HTMLTableCellElement> & { align?: "left" | "right" | "center" }) {
  const alignClass = align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left";
  return (
    <th
      className={cx(
        "px-4 py-3 text-[length:var(--fs-xs)] font-medium uppercase tracking-wider text-[var(--ui-muted)]",
        alignClass,
        className,
      )}
      {...props}
    >
      {children}
    </th>
  );
}

export function TCell({
  children,
  align = "left",
  className = "",
  ...props
}: TdHTMLAttributes<HTMLTableCellElement> & { align?: "left" | "right" | "center" }) {
  const alignClass = align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left";
  return (
    <td className={cx("px-4 py-3", alignClass, className)} {...props}>
      {children}
    </td>
  );
}
