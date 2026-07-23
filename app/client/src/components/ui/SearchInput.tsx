"use client";

import { Search } from "lucide-react";
import { cx } from "@/lib/cx";

/* Local Studio compact filter input — ported from
   .reference-LS-frontend/templates/nextjs-feature-demos/_shared/ui (SearchInput). */
export function SearchInput({
  value,
  onChange,
  placeholder = "Filter...",
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}) {
  return (
    <div className={cx("relative", className)}>
      <Search
        aria-hidden
        className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--ui-muted)]"
      />
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="h-8 w-full rounded-md border border-[var(--ui-border)] bg-[var(--ui-bg)] pl-8 pr-2.5 text-[length:var(--fs-sm)] text-[var(--ui-fg)] outline-none placeholder:text-[var(--ui-muted)] focus:border-[color-mix(in_srgb,var(--ui-info)_50%,transparent)]"
      />
    </div>
  );
}
