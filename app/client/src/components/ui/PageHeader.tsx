import type { ReactNode } from "react";

/* Local Studio page header grammar — ported from
   .reference-LS-frontend/templates/nextjs-feature-demos/_shared/ui (PageHeader). */
export function PageHeader({
  eyebrow,
  title,
  status,
  actions,
}: {
  eyebrow?: string;
  title: ReactNode;
  status?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-5 flex min-h-8 items-center justify-between gap-3">
      <div className="min-w-0">
        {eyebrow ? (
          <div className="text-[length:var(--fs-xs)] uppercase tracking-[0.14em] text-[var(--ui-muted)]">
            {eyebrow}
          </div>
        ) : null}
        <h2 className="mt-1 truncate text-[length:var(--fs-3xl)] font-medium tracking-[-0.02em] text-[var(--ui-fg)]">
          {title}
        </h2>
      </div>
      {(actions ?? status) ? (
        <div className="flex shrink-0 items-center gap-2 text-[length:var(--fs-sm)] text-[var(--ui-muted)]">
          {status}
          {actions}
        </div>
      ) : null}
    </div>
  );
}
