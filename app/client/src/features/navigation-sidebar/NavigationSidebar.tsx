"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FileText,
  LogOut,
  Menu,
  MessageSquare,
  Network,
  PanelLeftOpen,
  Search,
  Settings,
  Square,
  SquarePen,
  X,
} from "lucide-react";
import { cx, IconButton, SearchInput } from "@/_shared/ui";
import { AppLogo } from "@/components/ui/AppLogo";
import { useAuthStore } from "@/state/auth-store";
import { listConversations, type ConversationSummary } from "@/features/chat-shell/api";
import { SETTINGS_NAV_ITEM } from "@/features/navigation-sidebar/constants";
import { useNavigationSidebar, isRouteActive } from "@/features/navigation-sidebar/use-navigation-sidebar";

const navIcons = {
  chat: MessageSquare,
  library: FileText,
  graph: Network,
  settings: Settings,
} as const;

/* Local Studio left rail adapted for Context Engine: desktop resizable rail
   with collapse, Cmd/Ctrl+K conversation search, mobile top bar with a
   right slide-in drawer. Nav registry lives in constants.ts. */
export function NavigationSidebar() {
  const sidebar = useNavigationSidebar();
  const router = useRouter();
  const logout = useAuthStore((state) => state.logout);

  return (
    <>
      {!sidebar.expanded ? (
        <div className="fixed left-0 top-0 z-50 hidden h-9 w-10 items-center justify-center md:flex">
          <IconButton
            onClick={() => sidebar.setExpanded(true)}
            title="Expand sidebar"
            aria-label="Expand sidebar"
            className="text-(--dim)/70"
          >
            <PanelLeftOpen className="h-4 w-4" strokeWidth={1.75} />
          </IconButton>
        </div>
      ) : null}

      <aside
        className={cx(
          "relative z-40 hidden h-full shrink-0 flex-col overflow-hidden border-r border-(--border) bg-(--sidebar-bg) shadow-[inset_-1px_0_rgba(255,255,255,0.02)] md:flex",
          sidebar.resizing ? "" : "transition-[width] duration-150 ease-out",
          sidebar.expanded ? "" : "w-0 border-r-0",
        )}
        style={{ width: sidebar.expanded ? `${sidebar.width}px` : 0 }}
        aria-hidden={!sidebar.expanded}
      >
        {sidebar.expanded ? (
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize sidebar"
            title="Resize sidebar"
            onMouseDown={sidebar.startResize}
            className={cx(
              "absolute right-0 top-0 z-[60] h-full w-2 cursor-col-resize transition-colors",
              sidebar.resizing ? "bg-(--fg)/10" : "hover:bg-(--fg)/8",
            )}
          />
        ) : null}
        <div
          className={cx(
            "flex min-h-0 flex-1 flex-col overflow-hidden",
            sidebar.expanded ? "opacity-100" : "pointer-events-none opacity-0",
          )}
        >
          {sidebar.expanded ? (
            <>
              <div className="sticky top-0 z-50 flex min-h-16 shrink-0 items-center gap-2.5 border-b border-(--border)/35 bg-(--sidebar-bg) px-1.5 py-2.5">
                <AppLogo className="ml-1 h-12 w-12" />
                <span className="flex-1 truncate px-0.5 text-[length:var(--fs-sm)] font-medium text-(--dim)">
                  Context Engine
                </span>
                <IconButton
                  onClick={() => sidebar.setExpanded(false)}
                  title="Collapse sidebar"
                  aria-label="Collapse sidebar"
                >
                  <Square className="h-3.5 w-3.5" />
                </IconButton>
              </div>

              <nav className="flex min-h-0 flex-1 flex-col overflow-y-auto overflow-x-hidden px-2 py-0.5" aria-label="Application">
                <button
                  type="button"
                  onClick={() => router.push("/chat")}
                  className="mb-0.5 flex h-8 shrink-0 items-center gap-2.5 rounded-md px-2.5 text-(--color-foreground-subtle) transition-colors hover:bg-(--color-surface-hover) hover:text-(--fg)"
                  title="New chat"
                >
                  <SquarePen className="h-4 w-4 shrink-0 opacity-60" strokeWidth={1.5} />
                  <span className="flex-1 truncate text-left text-[length:var(--fs-lg)] font-normal">New chat</span>
                </button>
                <button
                  type="button"
                  onClick={() => sidebar.setSearchOpen(true)}
                  className="mb-1 flex h-8 shrink-0 items-center gap-2.5 rounded-md px-2.5 text-(--color-foreground-subtle) transition-colors hover:bg-(--color-surface-hover) hover:text-(--fg)"
                  title="Search conversations (⌘K)"
                >
                  <Search className="h-4 w-4 shrink-0 opacity-60" strokeWidth={1.5} />
                  <span className="flex-1 truncate text-left text-[length:var(--fs-lg)] font-normal">Search</span>
                </button>

                <div className="mb-1 mt-4 px-2.5 text-[length:var(--fs-sm)] font-normal text-(--color-foreground-subtlest)">
                  Workspace
                </div>
                {sidebar.items.map((item) => (
                  <NavItemDesktop key={item.href} href={item.href} label={item.label} icon={item.icon} active={item.active} />
                ))}
              </nav>

              <div className="shrink-0 px-2 py-2">
                <NavItemDesktop
                  href={SETTINGS_NAV_ITEM.href}
                  label={SETTINGS_NAV_ITEM.label}
                  icon={SETTINGS_NAV_ITEM.icon}
                  active={isRouteActive(sidebar.pathname, SETTINGS_NAV_ITEM.href)}
                />
                <button
                  type="button"
                  onClick={() => {
                    logout().catch(() => undefined);
                  }}
                  title="Logout"
                  className="group relative flex h-8 w-full shrink-0 items-center gap-2.5 rounded-md px-2.5 text-(--color-foreground-subtle) transition-colors hover:bg-(--color-surface-hover) hover:text-(--fg)"
                >
                  <LogOut className="h-4 w-4 shrink-0 opacity-60" strokeWidth={1.75} />
                  <span className="whitespace-nowrap text-[length:var(--fs-lg)] font-normal">Logout</span>
                </button>
              </div>
            </>
          ) : null}
        </div>
      </aside>

      {/* Mobile: top app bar + hamburger drawer. */}
      <div className="fixed left-0 right-0 top-0 z-40 flex h-14 items-center justify-between border-b border-(--border)/70 bg-(--bg) px-4 md:hidden">
        <span className="flex min-w-0 items-center gap-2">
          <AppLogo className="h-12 w-12" />
          <span className="truncate text-[length:var(--fs-base)] font-semibold tracking-tight text-(--fg)">
            Context Engine
          </span>
        </span>
        <button
          type="button"
          onClick={() => sidebar.setMobileOpen(true)}
          className="flex h-8 w-8 items-center justify-center rounded-md text-(--dim) transition-colors hover:bg-(--surface) hover:text-(--fg)"
          aria-label="Open navigation menu"
          aria-expanded={sidebar.mobileOpen}
          aria-controls="mobile-navigation-drawer"
        >
          <Menu className="h-[18px] w-[18px]" />
        </button>
      </div>

      {sidebar.mobileOpen ? (
        <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true">
          <button
            type="button"
            className="absolute inset-0 h-full w-full bg-black/60"
            aria-label="Close navigation menu"
            onClick={() => sidebar.setMobileOpen(false)}
          />
          <aside
            id="mobile-navigation-drawer"
            className="absolute right-0 top-0 flex h-full w-[min(22rem,88vw)] flex-col border-l border-(--border) bg-(--bg)"
          >
            <div className="flex h-12 shrink-0 items-center justify-between gap-3 border-b border-(--border) px-4">
              <div className="truncate text-sm font-semibold text-(--fg)">Navigation</div>
              <button
                type="button"
                onClick={() => sidebar.setMobileOpen(false)}
                className="flex h-10 w-10 items-center justify-center text-(--dim) hover:text-(--fg)"
                aria-label="Close navigation menu"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <nav className="min-h-0 flex-1 overflow-y-auto px-2 py-3">
              {[...sidebar.items, { ...SETTINGS_NAV_ITEM, active: isRouteActive(sidebar.pathname, "/settings") }].map(
                (item) => (
                  <NavItemMobile
                    key={item.href}
                    href={item.href}
                    label={item.label}
                    icon={item.icon}
                    active={item.active}
                    onNavigate={() => sidebar.setMobileOpen(false)}
                  />
                ),
              )}
            </nav>
          </aside>
        </div>
      ) : null}

      {sidebar.searchOpen ? (
        <ConversationSearchOverlay
          onClose={() => sidebar.setSearchOpen(false)}
          onSelect={() => {
            sidebar.setSearchOpen(false);
            router.push("/chat");
          }}
        />
      ) : null}
    </>
  );
}

/* Conversation search (⌘K) backed by GET /api/v1/conversations. */
function ConversationSearchOverlay({
  onClose,
  onSelect,
}: {
  onClose: () => void;
  onSelect: (conversation: ConversationSummary) => void;
}) {
  const [query, setQuery] = useState("");
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    listConversations()
      .then((rows) => {
        if (!cancelled) setConversations(rows);
      })
      .catch(() => {
        if (!cancelled) setConversations([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return conversations;
    return conversations.filter((row) => (row.title ?? "Untitled").toLowerCase().includes(needle));
  }, [conversations, query]);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/45 pt-24" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-lg border border-(--border) bg-(--color-popover) p-3 shadow-[var(--composer-shadow)]"
        onClick={(event) => event.stopPropagation()}
      >
        <SearchInput value={query} onChange={setQuery} placeholder="Search conversations..." />
        <div className="mt-3 max-h-72 space-y-1 overflow-y-auto">
          {loading ? (
            <div className="px-2 py-1.5 text-[length:var(--fs-sm)] text-(--dim)">Loading conversations.</div>
          ) : filtered.length === 0 ? (
            <div className="px-2 py-1.5 text-[length:var(--fs-sm)] text-(--dim)">No conversations found.</div>
          ) : (
            filtered.map((conversation) => (
              <button
                key={conversation.id}
                type="button"
                onClick={() => onSelect(conversation)}
                className="w-full rounded-md px-2 py-1.5 text-left text-[length:var(--fs-sm)] transition-colors hover:bg-(--hover)"
              >
                <div className="truncate text-(--fg)">{conversation.title ?? "Untitled"}</div>
                <div className="truncate font-mono text-[length:var(--fs-xs)] text-(--dim)">
                  {new Date(conversation.updatedAt).toLocaleString()}
                </div>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function NavItemDesktop({
  href,
  label,
  icon,
  active,
}: {
  href: string;
  label: string;
  icon: keyof typeof navIcons;
  active: boolean;
}) {
  const Icon = navIcons[icon];
  return (
    <Link
      href={href}
      title={label}
      aria-label={label}
      className={cx(
        "group relative flex h-8 shrink-0 items-center gap-2.5 rounded-md px-2.5 text-left transition-colors",
        active
          ? "bg-(--color-surface-hover) font-medium text-(--fg)"
          : "text-(--color-foreground-subtle) hover:bg-(--color-surface-hover) hover:text-(--fg)",
      )}
    >
      {active ? (
        <span aria-hidden className="absolute left-0 top-1/2 h-4 w-[2px] -translate-y-1/2 rounded-full bg-(--fg)/50" />
      ) : null}
      <Icon className={cx("h-4 w-4 shrink-0", active ? "text-(--fg)/85" : "opacity-60")} strokeWidth={1.75} />
      <span className="whitespace-nowrap text-[length:var(--fs-lg)]">{label}</span>
    </Link>
  );
}

function NavItemMobile({
  href,
  label,
  icon,
  active,
  onNavigate,
}: {
  href: string;
  label: string;
  icon: keyof typeof navIcons;
  active: boolean;
  onNavigate: () => void;
}) {
  const Icon = navIcons[icon];
  return (
    <Link
      href={href}
      onClick={onNavigate}
      className={cx(
        "mb-1 flex h-12 w-full items-center gap-3 border-l-2 px-2 text-left text-sm font-medium transition-colors",
        active ? "border-(--accent) text-(--fg)" : "border-transparent text-(--dim) hover:text-(--fg)",
      )}
    >
      <Icon className="h-5 w-5 shrink-0" />
      <span>{label}</span>
    </Link>
  );
}
