"use client";

import { cx } from "@/lib/cx";

export function SegmentedControl<T extends string>({
  items,
  value,
  onChange,
}: {
  items: Array<{ id: T; label: string }>;
  value: T;
  onChange: (id: T) => void;
}) {
  return (
    <div
      role="tablist"
      className="inline-flex h-7 items-center gap-0.5 rounded-[var(--rad-lg)] border border-[var(--ui-border)] bg-[var(--ui-bg)] p-0.5"
    >
      {items.map((item) => {
        const active = item.id === value;
        return (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(item.id)}
            className={cx(
              "inline-flex h-6 items-center rounded-[var(--rad-md)] px-2 text-[length:var(--fs-sm)] transition-colors",
              active ? "bg-[var(--ui-surface)] text-[var(--fg)]" : "text-[var(--dim)] hover:text-[var(--fg)]",
            )}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
