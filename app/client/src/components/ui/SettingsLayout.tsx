"use client";

import type { ReactNode } from "react";
import { RefreshCw } from "lucide-react";
import { cx } from "@/lib/cx";
import { PageHeader } from "@/components/ui/PageHeader";
import { ListGroup, ListRow, RowValue } from "@/components/ui/ListGroup";

/* Local Studio settings grammar — ported from
   .reference-LS-frontend/templates/nextjs-feature-demos/_shared/ui
   (SectionNav, RefreshIconButton, SettingsLayout, SettingsGroup,
   SettingsRow, SettingsValue). */

export type SettingsSectionId = string;

export type SectionNavItem<Id extends string = string> = {
  id: Id;
  label: string;
  description: string;
  icon: ReactNode;
};

export type SettingsSectionDef<Id extends SettingsSectionId = SettingsSectionId> = SectionNavItem<Id>;

export function SectionNav<Id extends string = string>({
  label,
  items,
  activeItem,
  onSelectItem,
}: {
  label: string;
  items: SectionNavItem<Id>[];
  activeItem: Id;
  onSelectItem: (item: Id) => void;
}) {
  return (
    <nav aria-label={label} className="pb-1">
      <div className="flex flex-wrap gap-1 lg:flex-col lg:flex-nowrap">
        {items.map((item) => {
          const active = activeItem === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelectItem(item.id)}
              className={cx(
                "group relative grid h-8 max-w-[calc(50%_-_0.125rem)] min-w-0 grid-cols-[18px_minmax(0,1fr)] items-center gap-2.5 rounded-md px-2.5 text-left text-[length:var(--fs-md)] transition-colors sm:max-w-none lg:w-full",
                active
                  ? "bg-[var(--color-surface)] text-[var(--ui-fg)]"
                  : "text-[var(--color-foreground-subtle)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--ui-fg)]",
              )}
              title={item.description}
            >
              {active ? (
                <span
                  aria-hidden
                  className="absolute left-0 top-1/2 h-3.5 w-[2px] -translate-y-1/2 rounded-full bg-[var(--color-sky-400)]"
                />
              ) : null}
              <span
                className={cx(
                  "flex h-4 w-4 items-center justify-center",
                  active ? "text-[var(--color-sky-400)] opacity-100" : "opacity-70",
                )}
              >
                {item.icon}
              </span>
              <span className={cx("truncate", active ? "font-medium" : "")}>{item.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}

export function RefreshIconButton({
  onClick,
  loading,
  label,
}: {
  onClick: () => void;
  loading?: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-[var(--ui-muted)] transition-colors hover:bg-[var(--ui-hover)] hover:text-[var(--ui-fg)] disabled:opacity-50"
      aria-label={label}
      title={label}
    >
      <RefreshCw className={cx("h-3.5 w-3.5", loading ? "animate-spin" : "")} aria-hidden />
    </button>
  );
}

export function SettingsLayout<Id extends SettingsSectionId = SettingsSectionId>({
  sections,
  activeSection,
  title,
  status,
  loading,
  onReload,
  onSelectSection,
  eyebrow = title,
  refreshLabel = `Refresh ${title.toLowerCase()}`,
  children,
}: {
  sections: SettingsSectionDef<Id>[];
  activeSection: Id;
  title: string;
  status: string;
  loading: boolean;
  onReload: () => void;
  onSelectSection: (section: Id) => void;
  eyebrow?: string;
  refreshLabel?: string;
  children: ReactNode;
}) {
  const activeLabel = sections.find((section) => section.id === activeSection)?.label ?? title;

  return (
    <div className="min-h-full overflow-y-auto overflow-x-hidden bg-[var(--ui-bg)] text-[var(--ui-fg)]">
      <div className="mx-auto grid w-full max-w-5xl grid-cols-1 gap-5 px-4 py-5 sm:px-6 lg:grid-cols-[200px_minmax(0,640px)] lg:gap-10 lg:py-8">
        <aside className="lg:sticky lg:top-6 lg:self-start">
          <div className="mb-4 flex items-start justify-between gap-3">
            <h1 className="text-[length:var(--fs-xl)] font-semibold tracking-[-0.01em] text-[var(--ui-fg)]">
              {title}
            </h1>
            <RefreshIconButton onClick={onReload} loading={loading} label={refreshLabel} />
          </div>
          <SectionNav
            label={`${title} sections`}
            items={sections}
            activeItem={activeSection}
            onSelectItem={onSelectSection}
          />
        </aside>
        <section className="min-w-0 pb-10">
          <PageHeader eyebrow={eyebrow} title={activeLabel} status={status} />
          <div className="space-y-0">{children}</div>
        </section>
      </div>
    </div>
  );
}

export function SettingsGroup({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <ListGroup title={title} description={description} actions={actions}>
      {children}
    </ListGroup>
  );
}

export function SettingsRow(props: Parameters<typeof ListRow>[0]) {
  return <ListRow {...props} />;
}

export function SettingsValue({
  children,
  mono = false,
  dim = false,
  truncate = false,
  wrap = false,
}: {
  children: ReactNode;
  mono?: boolean;
  dim?: boolean;
  truncate?: boolean;
  wrap?: boolean;
}) {
  return (
    <RowValue mono={mono} dim={dim} truncate={truncate} wrap={wrap}>
      {children}
    </RowValue>
  );
}
