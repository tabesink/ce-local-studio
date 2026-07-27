"use client";

/* Shared Local Studio UI primitives — ported one-to-one from
   .references/local-studio/frontend/src/ui/*. Components read tokens only;
   no hardcoded colors, radii, or row heights.

   Button / Input / StatusPill / StatusDot live in `@/ui` (P9-01 U2).
   This barrel re-exports those symbols and keeps residual mega-kit bodies. */

import {
  createContext,
  forwardRef,
  useContext,
  useId,
  useState,
  type CSSProperties,
  type Key,
  type ReactNode,
  type SelectHTMLAttributes,
  type TdHTMLAttributes,
  type TextareaHTMLAttributes,
  type ThHTMLAttributes,
} from "react";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  Info,
  RefreshCw,
  Search,
  TriangleAlert,
  X,
} from "lucide-react";
import {
  Button,
  StatusPill,
  type UiTone,
} from "@/ui";
import { cx } from "@/ui/cx";

export { cx } from "@/ui/cx";
export {
  Button,
  type ButtonProps,
  type ButtonSize,
  type ButtonVariant,
  Input,
  type InputProps,
  StatusDot,
  StatusPill,
  type StatusPillVariant,
  type UiTone,
} from "@/ui";

/* ────────────────────────────── page ────────────────────────────── */

export type SectionNavItem<Id extends string = string> = {
  id: Id;
  label: string;
  description: string;
  icon: ReactNode;
};

export function AppPage({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <main
      className={cx(
        "min-h-full overflow-y-auto overflow-x-hidden bg-(--ui-bg) text-(--ui-fg)",
        className,
      )}
    >
      {children}
    </main>
  );
}

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
          <div className="text-[length:var(--fs-xs)] uppercase tracking-[0.14em] text-(--ui-muted)">
            {eyebrow}
          </div>
        ) : null}
        <h2 className="mt-1 truncate text-[length:var(--fs-3xl)] font-medium tracking-[-0.02em] text-(--ui-fg)">
          {title}
        </h2>
      </div>
      {(actions ?? status) ? (
        <div className="flex shrink-0 items-center gap-2 text-[length:var(--fs-sm)] text-(--ui-muted)">
          {status}
          {actions}
        </div>
      ) : null}
    </div>
  );
}

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
                  ? "bg-(--color-surface) text-(--ui-fg)"
                  : "text-(--color-foreground-subtle) hover:bg-(--color-surface-hover) hover:text-(--ui-fg)",
              )}
              title={item.description}
            >
              {active ? (
                <span
                  aria-hidden
                  className="absolute left-0 top-1/2 h-3.5 w-[2px] -translate-y-1/2 rounded-full bg-(--color-sky-400)"
                />
              ) : null}
              <span
                className={cx(
                  "flex h-4 w-4 items-center justify-center",
                  active ? "text-(--color-sky-400) opacity-100" : "opacity-70",
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
      className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-(--ui-muted) transition-colors hover:bg-(--ui-hover) hover:text-(--ui-fg) disabled:opacity-50"
      aria-label={label}
      title={label}
    >
      <RefreshCw className={cx("h-3.5 w-3.5", loading ? "animate-spin" : "")} />
    </button>
  );
}

/* ────────────────────────────── button ────────────────────────────── */

/* Compact h-7 control used across settings-like rows. */
export function SettingsButton({
  children,
  onClick,
  disabled,
  title,
  tone = "default",
  type = "button",
  "aria-label": ariaLabel,
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  title?: string;
  tone?: "default" | "primary" | "danger";
  type?: "button" | "submit";
  "aria-label"?: string;
}) {
  const classes =
    tone === "primary"
      ? "bg-(--ui-fg)/90 text-(--ui-bg) hover:bg-(--ui-fg)"
      : tone === "danger"
        ? "text-(--ui-danger) hover:bg-(--ui-danger)/10"
        : "text-(--ui-muted) hover:text-(--ui-fg) hover:bg-(--ui-hover)";

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={ariaLabel}
      className={cx(
        "inline-flex h-7 items-center justify-center gap-1.5 rounded-md px-2.5 text-[length:var(--fs-sm)] font-normal transition-colors disabled:pointer-events-none disabled:opacity-45",
        classes,
      )}
    >
      {children}
    </button>
  );
}

/* Compact 28px icon-only control (sidebar/header idiom). */
export function IconButton({
  children,
  onClick,
  title,
  disabled,
  className,
  "aria-label": ariaLabel,
  "aria-expanded": ariaExpanded,
  "aria-controls": ariaControls,
}: {
  children: ReactNode;
  onClick?: () => void;
  title?: string;
  disabled?: boolean;
  className?: string;
  "aria-label"?: string;
  "aria-expanded"?: boolean;
  "aria-controls"?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={ariaLabel ?? title}
      aria-expanded={ariaExpanded}
      aria-controls={ariaControls}
      disabled={disabled}
      className={cx(
        "flex h-7 w-7 items-center justify-center rounded-md text-(--dim) transition-colors hover:bg-(--hover) hover:text-(--fg) disabled:opacity-50",
        className,
      )}
    >
      {children}
    </button>
  );
}

/* Canonical compact on/off control for dense settings and list rows. */
export function ToggleSwitch({
  checked,
  onCheckedChange,
  disabled = false,
  className,
  title,
  "aria-label": ariaLabel,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
  title?: string;
  "aria-label": string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      title={title}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cx(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors disabled:pointer-events-none disabled:opacity-45",
        checked
          ? "border-(--ui-accent)/40 bg-(--ui-accent)/15"
          : "border-(--ui-separator) bg-(--ui-bg)",
        className,
      )}
    >
      <span
        aria-hidden
        className={cx(
          "h-3.5 w-3.5 rounded-full shadow-sm transition-transform",
          checked ? "translate-x-[18px] bg-(--ui-accent)" : "translate-x-1 bg-(--ui-muted)",
        )}
      />
    </button>
  );
}

/* ────────────────────────────── tabs ────────────────────────────── */

export type TabVariant = "underline" | "pill" | "button-group";

export interface TabItem<T extends string = string> {
  id: T;
  label: string;
  icon?: ReactNode;
}

export function Tabs<T extends string = string>({
  variant = "underline",
  items,
  activeTab,
  onSelectTab,
  className = "",
}: {
  variant?: TabVariant;
  items: TabItem<T>[];
  activeTab: T;
  onSelectTab: (tab: T) => void;
  className?: string;
}) {
  if (variant === "underline") {
    return (
      <div className={`flex gap-1 ${className}`}>
        {items.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => onSelectTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 ${
              activeTab === tab.id
                ? "border-(--ui-accent) text-(--ui-fg)"
                : "border-transparent text-(--ui-muted) hover:text-(--ui-fg)"
            }`}
          >
            {tab.icon && <span className="mr-2 inline">{tab.icon}</span>}
            {tab.label}
          </button>
        ))}
      </div>
    );
  }

  if (variant === "pill") {
    return (
      <div className={`flex gap-1 overflow-x-auto ${className}`}>
        {items.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => onSelectTab(tab.id)}
            className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-sm whitespace-nowrap transition-colors ${
              activeTab === tab.id
                ? "bg-(--color-tab-active) font-medium text-(--fg)"
                : "text-(--color-foreground-subtle) hover:bg-(--color-tab) hover:text-(--fg)"
            }`}
          >
            {tab.icon}
            <span>{tab.label}</span>
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className={`overflow-x-auto ${className}`}>
      <div className="flex min-w-max items-center gap-2 rounded-lg border border-(--ui-border) bg-(--ui-bg) p-1">
        {items.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => onSelectTab(tab.id)}
            className={`flex items-center gap-2 rounded-md px-4 py-2 text-xs whitespace-nowrap border transition-colors sm:text-sm ${
              activeTab === tab.id
                ? "border-(--ui-info)/40 bg-(--ui-info)/15 text-(--ui-fg)"
                : "border-transparent text-(--ui-muted) hover:border-(--ui-border) hover:text-(--ui-fg)"
            }`}
          >
            {tab.icon}
            <span>{tab.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export interface SegmentedItem<T extends string = string> {
  id: T;
  label: string;
  icon?: ReactNode;
}

/** Standardized segmented control (pill-in-a-track) for small mode choices. */
export function SegmentedControl<T extends string = string>({
  items,
  value,
  onChange,
  size = "md",
  className,
}: {
  items: SegmentedItem<T>[];
  value: T;
  onChange: (id: T) => void;
  size?: "sm" | "md";
  className?: string;
}) {
  return (
    <div
      role="tablist"
      className={cx(
        "inline-flex items-center gap-0.5 rounded-lg border border-(--ui-border) bg-(--ui-bg) p-0.5",
        className,
      )}
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
              "inline-flex items-center gap-1.5 rounded-md transition-colors",
              size === "sm"
                ? "px-2 py-0.5 text-[length:var(--fs-sm)]"
                : "px-2.5 py-1 text-[length:var(--fs-md)]",
              active
                ? "bg-(--ui-surface) text-(--ui-fg) shadow-sm"
                : "text-(--ui-muted) hover:text-(--ui-fg)",
            )}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/* ────────────────────────────── list ────────────────────────────── */

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
              className="group flex items-center gap-1.5 text-(--ui-muted) hover:text-(--ui-fg)"
            >
              <ChevronDown
                className={cx("h-3 w-3 transition-transform", open ? "" : "-rotate-90")}
                aria-hidden
              />
              <h3 className="text-[length:var(--fs-md)] font-semibold tracking-[-0.005em]">
                {title}
              </h3>
            </button>
          ) : (
            <h3 className="text-[length:var(--fs-md)] font-semibold tracking-[-0.005em] text-(--ui-muted)">
              {title}
            </h3>
          )}
          {actions ? <div className="shrink-0">{actions}</div> : null}
        </div>
      ) : null}
      {showBody ? (
        <div className="overflow-hidden rounded-md border border-(--ui-border) bg-(--ui-surface) shadow-[0_1px_0_rgba(255,255,255,0.025)_inset] [&>*+*]:before:pointer-events-none [&>*+*]:before:absolute [&>*+*]:before:left-0 [&>*+*]:before:right-0 [&>*+*]:before:top-0 [&>*+*]:before:h-px [&>*+*]:before:bg-(--ui-separator) [&>*]:relative">
          {children}
        </div>
      ) : null}
      {description && showBody ? (
        <p className="mt-1.5 px-3.5 text-[length:var(--fs-sm)] leading-relaxed text-(--ui-muted)">
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
      <div className={cx("px-3.5 py-3 transition-colors hover:bg-(--ui-hover)/35", className)}>
        <div className="grid min-w-0 grid-cols-1 gap-2.5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
          <div className="min-w-0 space-y-1">
            <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
              <div
                className="min-w-0 break-words text-[length:var(--fs-base)] font-medium leading-snug text-(--ui-fg)"
                title={label}
              >
                {label}
              </div>
            </div>
            {description ? (
              <div className="line-clamp-2 text-[length:var(--fs-sm)] leading-relaxed text-(--ui-muted)">
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
        {primaryValue ? <div className="mt-2 min-w-0 text-(--ui-muted)">{primaryValue}</div> : null}
        {children ? (
          <div className="mt-2 min-w-0 space-y-1.5 border-t border-(--ui-separator)/70 pt-2 text-[length:var(--fs-sm)] leading-relaxed">
            {children}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className={cx("px-3.5 py-2.5 transition-colors hover:bg-(--ui-hover)/35", className)}>
      {/* Shared 2-column grid pins a fixed label column so controls align
          vertically across rows; expanded children indent to the control column. */}
      <div className="grid min-h-7 grid-cols-1 gap-1.5 md:grid-cols-[minmax(160px,0.42fr)_minmax(0,1fr)] md:items-center md:gap-5">
        <div className="min-w-0">
          <div
            className="truncate text-[length:var(--fs-base)] font-medium text-(--ui-fg)"
            title={label}
          >
            {label}
          </div>
          {description ? (
            <div className="mt-0.5 text-[length:var(--fs-sm)] leading-relaxed text-(--ui-muted)">
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
  const value =
    children === null || children === undefined || children === "" ? "Not set" : children;
  return (
    <div
      className={cx(
        "text-[length:var(--fs-base)]",
        mono ? "font-mono text-[length:var(--fs-md)]" : "",
        dim ? "text-(--ui-muted)" : "text-(--ui-fg)/80",
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
    <div className="px-3.5 py-2.5 text-[length:var(--fs-md)] leading-relaxed text-(--ui-muted)">
      {children}
    </div>
  );
}

export function KeyValueRow({
  label,
  value,
  className,
}: {
  label: ReactNode;
  value: ReactNode;
  className?: string;
}) {
  return (
    <div className={cx("flex items-baseline justify-between gap-3 text-xs", className)}>
      <dt className="text-(--ui-muted)">{label}</dt>
      <dd className="min-w-0 truncate text-right font-mono text-(--ui-fg)">{value}</dd>
    </div>
  );
}

/* ────────────────────────────── settings ────────────────────────────── */

export type SettingsSectionId = string;
export type SettingsSectionDef<Id extends SettingsSectionId = SettingsSectionId> =
  SectionNavItem<Id>;

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
    <AppPage>
      <div className="mx-auto grid w-full max-w-5xl grid-cols-1 gap-5 px-4 py-5 sm:px-6 lg:grid-cols-[200px_minmax(0,640px)] lg:gap-10 lg:py-8">
        <aside className="lg:sticky lg:top-6 lg:self-start">
          <div className="mb-4 flex items-start justify-between gap-3">
            <h1 className="text-[length:var(--fs-xl)] font-semibold tracking-[-0.01em] text-(--ui-fg)">
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
    </AppPage>
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

export type SettingsFactRow = {
  label: string;
  value: ReactNode;
  key?: string | number;
  description?: ReactNode;
  variant?: "settings" | "resource";
  mono?: boolean;
  dim?: boolean;
  truncate?: boolean;
  wrap?: boolean;
  status?: { label: ReactNode; tone?: UiTone };
  actions?: ReactNode;
  children?: ReactNode;
};

export function SettingsFactRows({ rows }: { rows: SettingsFactRow[] }) {
  return (
    <>
      {rows.map((row) => (
        <SettingsRow
          key={row.key ?? row.label}
          variant={row.variant}
          label={row.label}
          description={row.description}
          value={
            <SettingsValue mono={row.mono} dim={row.dim} truncate={row.truncate} wrap={row.wrap}>
              {row.value}
            </SettingsValue>
          }
          status={
            row.status ? (
              <StatusPill tone={row.status.tone}>{row.status.label}</StatusPill>
            ) : undefined
          }
          actions={row.actions}
        >
          {row.children}
        </SettingsRow>
      ))}
    </>
  );
}

const noticeClasses: Record<UiTone, string> = {
  default: "border-(--ui-border) bg-(--ui-hover)/40 text-(--ui-muted)",
  good: "border-(--ui-success)/30 bg-(--ui-success)/10 text-(--ui-success)",
  warning: "border-(--ui-warning)/30 bg-(--ui-warning)/10 text-(--ui-warning)",
  danger: "border-(--ui-danger)/30 bg-(--ui-danger)/10 text-(--ui-danger)",
  info: "border-(--ui-info)/30 bg-(--ui-info)/10 text-(--ui-info)",
};

export function SettingsNotice({
  children,
  tone = "info",
  className,
}: {
  children: ReactNode;
  tone?: UiTone;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "rounded-md border px-3 py-2 text-[length:var(--fs-sm)] leading-relaxed",
        noticeClasses[tone],
        className,
      )}
    >
      {children}
    </div>
  );
}

export function SettingsActions({
  children,
  flush = false,
  className,
}: {
  children: ReactNode;
  flush?: boolean;
  className?: string;
}) {
  return (
    <div className={cx("flex justify-end gap-1", flush ? "" : "px-3.5 py-2", className)}>
      {children}
    </div>
  );
}

export function SettingsInput({
  id,
  value,
  onChange,
  onBlur,
  placeholder,
  type = "text",
  className = "",
  "aria-label": ariaLabel,
}: {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  placeholder?: string;
  type?: "text" | "password";
  className?: string;
  "aria-label"?: string;
}) {
  return (
    <input
      id={id}
      type={type}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      onBlur={onBlur}
      placeholder={placeholder}
      aria-label={ariaLabel}
      className={cx(
        "h-7 w-full rounded-md border border-(--ui-separator) bg-(--ui-bg) px-2.5 text-[length:var(--fs-base)] text-(--ui-fg) outline-none transition placeholder:text-(--ui-muted)/50 focus:border-(--ui-accent)/40",
        className,
      )}
    />
  );
}

export function SettingsTextarea({
  value,
  onChange,
  placeholder,
  rows = 3,
  className = "",
  mono = false,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
  className?: string;
  mono?: boolean;
}) {
  return (
    <textarea
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      rows={rows}
      className={cx(
        "w-full resize-none rounded-md border border-(--ui-separator) bg-(--ui-bg) px-2.5 py-1.5 text-[length:var(--fs-base)] text-(--ui-fg) outline-none placeholder:text-(--ui-muted)/50 focus:border-(--ui-accent)/40",
        mono ? "font-mono text-[length:var(--fs-sm)]" : "",
        className,
      )}
    />
  );
}

/* ────────────────────────────── forms ────────────────────────────── */

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options?: SelectOption[];
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, options, placeholder, children, className = "", id, ...props },
  ref,
) {
  const selectId = id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

  return (
    <div>
      {label && (
        <label
          htmlFor={selectId}
          className="mb-2 block text-xs font-medium uppercase tracking-wider text-(--ui-muted)"
        >
          {label}
        </label>
      )}
      <select
        ref={ref}
        id={selectId}
        className={`h-8 w-full rounded-md border border-(--ui-separator) bg-(--ui-bg) px-2.5 text-[length:var(--fs-base)] text-(--ui-fg) transition-all focus:border-(--ui-info)/50 focus:outline-none focus:ring-1 focus:ring-(--ui-info)/20 ${className}`}
        {...props}
      >
        {placeholder && <option value="">{placeholder}</option>}
        {options
          ? options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))
          : children}
      </select>
    </div>
  );
});

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className = "", ...props }, ref) {
  return (
    <textarea
      ref={ref}
      className={`w-full rounded-md border border-(--ui-separator) bg-(--ui-bg) px-2.5 py-1.5 text-[length:var(--fs-base)] text-(--ui-fg) transition-all placeholder:text-(--ui-muted)/50 focus:border-(--ui-info)/50 focus:outline-none focus:ring-1 focus:ring-(--ui-info)/20 ${className}`}
      {...props}
    />
  );
});

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
      <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-(--ui-muted)" />
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="h-8 w-full rounded-md border border-(--ui-border) bg-(--ui-bg) pl-8 pr-2.5 text-[length:var(--fs-sm)] text-(--ui-fg) outline-none placeholder:text-(--ui-muted) focus:border-(--ui-info)/50"
      />
    </div>
  );
}

export function Checkbox({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}) {
  return (
    <label className="inline-flex items-center gap-1.5 text-[length:var(--fs-sm)] text-(--ui-muted)">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-3.5 w-3.5 accent-(--ui-info)"
      />
      {label}
    </label>
  );
}

/* ────────────────────────────── table ────────────────────────────── */

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
        bordered ? "overflow-hidden rounded-[var(--ui-radius)] border border-(--ui-border)" : "",
        className,
      )}
    >
      <table className={cx("w-full text-left", tableClassName)}>{children}</table>
    </div>
  );
}

export function THead({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <thead className={cx("border-b border-(--ui-border) bg-(--ui-surface)", className)}>
      {children}
    </thead>
  );
}

export function TBody({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <tbody className={cx("divide-y divide-(--ui-border)", className)}>{children}</tbody>;
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
          ? "cursor-pointer hover:bg-(--ui-hover)"
          : "hover:bg-(--ui-surface)/50",
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
  const alignClass =
    align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left";
  return (
    <th
      className={cx(
        "px-4 py-3 text-xs font-medium uppercase tracking-wider text-(--ui-muted)",
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
  const alignClass =
    align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left";
  return (
    <td className={cx("px-4 py-3", alignClass, className)} {...props}>
      {children}
    </td>
  );
}

/* ────────────────────────────── misc ────────────────────────────── */

export function ProgressBar({
  progress,
  tone = "default",
  role = "progressbar",
  className,
  trackClassName,
  barClassName,
  "aria-label": ariaLabel,
  "aria-valuetext": ariaValueText,
}: {
  progress: number;
  tone?: UiTone;
  role?: "progressbar" | "meter";
  className?: string;
  trackClassName?: string;
  barClassName?: string;
  "aria-label"?: string;
  "aria-valuetext"?: string;
}) {
  const pct = Math.min(100, Math.max(0, progress));
  const toneClass =
    tone === "good"
      ? "bg-(--ui-success)"
      : tone === "warning"
        ? "bg-(--ui-warning)"
        : tone === "danger"
          ? "bg-(--ui-danger)"
          : tone === "info"
            ? "bg-(--ui-info)"
            : "bg-(--ui-fg)/40";
  return (
    <div
      role={role}
      aria-label={ariaLabel}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      aria-valuetext={ariaValueText}
      className={cx(
        "h-1 w-full overflow-hidden rounded-full bg-(--ui-fg)/15",
        className,
        trackClassName,
      )}
    >
      <div
        className={cx("h-full rounded-full transition-all duration-300", toneClass, barClassName)}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function Stat({
  label,
  value,
  className,
}: {
  label: ReactNode;
  value: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "min-w-0 border-r border-(--ui-border)/40 pr-2 pl-3 first:pl-0 last:border-r-0 sm:pr-4 sm:pl-5",
        className,
      )}
    >
      <dt className="truncate font-mono text-[length:var(--fs-2xs)] font-medium uppercase tracking-[0.18em] text-(--ui-muted)/75">
        {label}
      </dt>
      <dd className="mt-1 font-mono text-[length:var(--fs-xl)] leading-none tabular-nums text-(--ui-fg)">
        {value}
      </dd>
    </div>
  );
}

export function SectionLabel({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cx(
        "text-[length:var(--fs-xs)] font-medium uppercase tracking-[var(--section-tracking)] text-(--ui-muted)",
        className,
      )}
    >
      {children}
    </div>
  );
}

/* ────────────────────────────── card ────────────────────────────── */

export type CardPadding = "sm" | "md" | "lg";

const cardPaddingClasses: Record<CardPadding, string> = {
  sm: "p-3",
  md: "p-4",
  lg: "p-6",
};

export function Card({
  padding = "md",
  children,
  className = "",
  bordered = true,
}: {
  padding?: CardPadding;
  children: ReactNode;
  className?: string;
  bordered?: boolean;
}) {
  return (
    <div
      className={cx(
        "rounded-lg bg-(--ui-bg)",
        bordered ? "border border-(--ui-border)" : "",
        cardPaddingClasses[padding],
        className,
      )}
    >
      {children}
    </div>
  );
}

/* ────────────────────────────── alert ────────────────────────────── */

export type AlertVariant = "info" | "success" | "warning" | "error";

const alertVariantConfig: Record<AlertVariant, { classes: string; DefaultIcon: typeof Info }> = {
  info: { classes: "border-(--ui-info)/30 bg-(--ui-info)/10 text-(--ui-info)", DefaultIcon: Info },
  success: {
    classes: "border-(--ui-success)/30 bg-(--ui-success)/10 text-(--ui-success)",
    DefaultIcon: CheckCircle2,
  },
  warning: {
    classes: "border-(--ui-warning)/30 bg-(--ui-warning)/10 text-(--ui-warning)",
    DefaultIcon: TriangleAlert,
  },
  error: {
    classes: "border-(--ui-danger)/30 bg-(--ui-danger)/10 text-(--ui-danger)",
    DefaultIcon: AlertCircle,
  },
};

export function Alert({
  variant = "info",
  icon,
  children,
  className = "",
}: {
  variant?: AlertVariant;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const config = alertVariantConfig[variant];
  const IconComponent = config.DefaultIcon;
  return (
    <div className={cx("rounded-lg border p-4", config.classes, className)}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5 shrink-0">{icon || <IconComponent className="h-4 w-4" />}</div>
        <div className="text-sm">{children}</div>
      </div>
    </div>
  );
}

/* ────────────────────────────── fact grid ────────────────────────────── */

export type FactGridItem = {
  label: ReactNode;
  value: ReactNode;
  key?: Key;
  span?: "full";
  mono?: boolean;
};

export type FactGridColumns = 1 | 2 | 3 | 4;
export type FactGridVariant = "plain" | "panel";

const factGridColumnClasses: Record<FactGridColumns, string> = {
  1: "",
  2: "md:grid-cols-2",
  3: "md:grid-cols-3",
  4: "md:grid-cols-4",
};

export function FactGrid({
  items,
  columns = 2,
  variant = "plain",
  className,
}: {
  items: FactGridItem[];
  columns?: FactGridColumns;
  variant?: FactGridVariant;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "grid gap-3 text-[length:var(--fs-sm)]",
        factGridColumnClasses[columns],
        variant === "panel" ? "rounded-md border border-(--ui-border) bg-(--ui-hover)/35 p-3" : "",
        className,
      )}
    >
      {items.map((item, index) => (
        <div key={item.key ?? index} className={item.span === "full" ? "md:col-span-full" : ""}>
          <div className="mb-1 text-[length:var(--fs-xs)] text-(--ui-muted)">{item.label}</div>
          <div
            className={cx(
              "break-words text-(--ui-fg) [overflow-wrap:anywhere]",
              item.mono ? "font-mono" : "",
            )}
          >
            {item.value}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ────────────────────────────── modal ────────────────────────────── */

const UiModalTitleIdContext = createContext<string | null>(null);

export function UiModal({
  isOpen,
  onClose,
  children,
  className,
  maxWidth = "max-w-lg",
}: {
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
  className?: string;
  maxWidth?: string;
}) {
  const titleId = useId();

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <button
        className="absolute inset-0 z-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
        aria-label="Close"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={cx(
          "relative z-10 w-full rounded-xl border border-(--ui-border) bg-(--ui-surface) shadow-xl",
          maxWidth,
          className,
        )}
      >
        <UiModalTitleIdContext.Provider value={titleId}>{children}</UiModalTitleIdContext.Provider>
      </div>
    </div>
  );
}

export function UiModalHeader({
  title,
  icon,
  onClose,
  actions,
  closeLabel = "Close",
  className,
  showCloseButton = true,
}: {
  title: string;
  icon?: ReactNode;
  onClose?: () => void;
  actions?: ReactNode;
  closeLabel?: string;
  className?: string;
  showCloseButton?: boolean;
}) {
  const titleId = useContext(UiModalTitleIdContext);
  return (
    <div
      className={cx(
        "flex items-center justify-between border-b border-(--ui-border) px-6 py-4",
        className,
      )}
    >
      <div className="flex items-center gap-2">
        {icon}
        <h2 id={titleId ?? undefined} className="text-lg font-semibold">
          {title}
        </h2>
      </div>
      <div className="flex items-center gap-2">
        {actions}
        {showCloseButton && onClose ? (
          <button
            onClick={onClose}
            className="rounded p-1.5 hover:bg-(--ui-hover)"
            aria-label={closeLabel}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        ) : null}
      </div>
    </div>
  );
}

/* ────────────────────────────── drawer ────────────────────────────── */

/* Right-anchored side panel (recipe editor, detail editors). Chrome lives
   here so every drawer matches; callers only supply content and actions. */
export function Drawer({
  children,
  width = 720,
  className,
  style,
}: {
  children: ReactNode;
  width?: number;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <aside
      className={cx(
        "relative flex shrink-0 flex-col border-l border-(--ui-border) bg-(--ui-bg)",
        className,
      )}
      style={{
        width: `${width}px`,
        minWidth: "min(420px, 40%)",
        maxWidth: "min(960px, 76%)",
        ...style,
      }}
    >
      {children}
    </aside>
  );
}

export function DrawerHeader({
  title,
  badge,
  onClose,
  className,
}: {
  title: ReactNode;
  badge?: ReactNode;
  onClose?: () => void;
  className?: string;
}) {
  return (
    <header
      className={cx(
        "flex h-9 shrink-0 items-center gap-2 border-b border-(--ui-border) px-2 text-[length:var(--fs-sm)]",
        className,
      )}
    >
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <span className="truncate font-medium text-(--ui-fg)/85">{title}</span>
        {badge}
      </div>
      {onClose ? (
        <Button variant="icon" size="sm" onClick={onClose} aria-label="Close" title="Close">
          <X className="h-3 w-3" />
        </Button>
      ) : null}
    </header>
  );
}

export function DrawerBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx("min-h-0 flex-1 overflow-y-auto p-4", className)}>{children}</div>;
}

export function DrawerFooter({
  status,
  children,
  className,
}: {
  status?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <footer
      className={cx(
        "flex h-10 shrink-0 items-center justify-between gap-3 border-t border-(--ui-border) bg-(--ui-bg) px-2 text-[length:var(--fs-sm)]",
        className,
      )}
    >
      <div className="min-w-0 truncate text-(--ui-muted)/75">{status}</div>
      {children ? <div className="flex shrink-0 items-center gap-1">{children}</div> : null}
    </footer>
  );
}

/* ────────────────────────────── model page ────────────────────────────── */

/* Model-page grammar from .references/local-studio/frontend/src/ui/model-page.tsx.
   The recipes/models surface is built entirely on these rows. */

export type ModelStatusTone = UiTone;
export type ModelRowHighlight = "none" | "success";

export function ModelSection({
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
    <section className="min-w-0">
      <div className="flex min-h-9 items-end justify-between gap-4 border-b border-(--ui-border)/75 pb-2">
        <div className="min-w-0">
          <h3 className="text-[length:var(--fs-md)] font-medium text-(--ui-fg)">{title}</h3>
          {description ? (
            <p className="mt-0.5 text-[length:var(--fs-sm)] text-(--ui-muted)">{description}</p>
          ) : null}
        </div>
        {actions ? <div className="shrink-0">{actions}</div> : null}
      </div>
      <div className="divide-y divide-(--ui-border)/55">{children}</div>
    </section>
  );
}

export function ModelRow({
  label,
  description,
  leading,
  value,
  control,
  status,
  actions,
  children,
  highlight = "none",
  className,
  onClick,
}: {
  label: string;
  description?: string;
  leading?: ReactNode;
  value?: ReactNode;
  control?: ReactNode;
  status?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  highlight?: ModelRowHighlight;
  className?: string;
  onClick?: () => void;
}) {
  const interactive = Boolean(onClick);
  return (
    <div
      className={cx(
        "group px-1 py-2.5 transition-colors hover:bg-(--ui-hover)/35",
        interactive
          ? "cursor-pointer rounded-md focus:outline-none focus:ring-1 focus:ring-(--ui-info)/45"
          : "",
        highlight === "success" ? "model-row-shine" : "",
        className,
      )}
      onClick={onClick}
      onKeyDown={
        interactive
          ? (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onClick?.();
              }
            }
          : undefined
      }
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
    >
      <div className="grid min-h-7 grid-cols-1 gap-2 md:grid-cols-[minmax(150px,0.44fr)_minmax(0,1fr)] md:items-center md:gap-5">
        <div className="flex min-w-0 items-center gap-2.5">
          {leading ? <span className="shrink-0">{leading}</span> : null}
          <div className="min-w-0">
            <div
              className="truncate text-[length:var(--fs-md)] font-medium text-(--ui-fg)"
              title={label}
            >
              {label}
            </div>
            {description ? (
              <div
                className="mt-0.5 truncate text-[length:var(--fs-sm)] text-(--ui-muted)"
                title={description}
              >
                {description}
              </div>
            ) : null}
          </div>
        </div>
        <div className="flex min-w-0 items-center justify-between gap-3">
          <div
            className="min-w-0 flex-1"
            onClick={control && interactive ? (event) => event.stopPropagation() : undefined}
          >
            {control ?? value ?? <ModelValue dim>Not reported yet</ModelValue>}
          </div>
          {status ? (
            <div
              className="shrink-0"
              onClick={interactive ? (event) => event.stopPropagation() : undefined}
            >
              {status}
            </div>
          ) : null}
          {actions ? (
            <div
              className="flex shrink-0 items-center gap-1"
              onClick={interactive ? (event) => event.stopPropagation() : undefined}
            >
              {actions}
            </div>
          ) : null}
        </div>
      </div>
      {children ? <div className="mt-2 md:ml-[calc(150px+1.25rem)]">{children}</div> : null}
    </div>
  );
}

export function ModelValue({
  children,
  mono = false,
  dim = false,
}: {
  children: ReactNode;
  mono?: boolean;
  dim?: boolean;
}) {
  return (
    <div
      className={cx(
        "truncate text-[length:var(--fs-md)]",
        mono ? "font-mono" : "",
        dim ? "text-(--ui-muted)" : "text-(--ui-fg)",
      )}
      title={typeof children === "string" ? children : undefined}
    >
      {children || "Not set"}
    </div>
  );
}

export function ModelStatus({
  tone = "default",
  children,
}: {
  tone?: ModelStatusTone;
  children: ReactNode;
}) {
  return (
    <StatusPill tone={tone} variant="dot" className="text-[length:var(--fs-xs)]">
      {children}
    </StatusPill>
  );
}

export function ModelButton({
  children,
  onClick,
  disabled,
  title,
  tone = "default",
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  title?: string;
  tone?: "default" | "primary" | "danger";
  type?: "button" | "submit";
}) {
  const classes =
    tone === "primary"
      ? "text-(--ui-fg) hover:bg-(--ui-hover)"
      : tone === "danger"
        ? "text-(--ui-danger) hover:bg-(--ui-danger)/10"
        : "text-(--ui-muted) hover:bg-(--ui-hover) hover:text-(--ui-fg)";
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={cx(
        "inline-flex h-6 items-center justify-center gap-1.5 rounded-md px-1.5 text-[length:var(--fs-sm)] font-medium transition-colors disabled:pointer-events-none disabled:opacity-45",
        classes,
      )}
    >
      {children}
    </button>
  );
}

export function ModelInput({
  value,
  onChange,
  placeholder,
  type = "text",
  className = "",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: "text" | "password";
  className?: string;
}) {
  return (
    <input
      type={type}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      className={cx(
        "h-7 w-full rounded-md border border-transparent bg-(--ui-surface) px-2.5 text-[length:var(--fs-md)] text-(--ui-fg) outline-none transition placeholder:text-(--ui-muted)/65 focus:bg-(--ui-bg) focus:ring-1 focus:ring-(--ui-info)/60",
        className,
      )}
    />
  );
}
