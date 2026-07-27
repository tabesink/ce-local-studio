"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import { usePathname } from "next/navigation";
import { readUiPreference, writeUiPreference } from "@/lib/storage";
import { useAuthStore } from "@/features/auth/auth-store";
import {
  NAV_ITEMS,
  SIDEBAR_DEFAULT_WIDTH,
  SIDEBAR_MAX_WIDTH,
  SIDEBAR_MIN_WIDTH,
} from "@/features/navigation-sidebar/constants";

function clampSidebarWidth(width: number): number {
  if (!Number.isFinite(width)) return SIDEBAR_DEFAULT_WIDTH;
  return Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, Math.round(width)));
}

export function isRouteActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname.startsWith(href);
}

function readStoredWidth(): number {
  try {
    const raw = readUiPreference("ce.panelWidths");
    if (!raw) return SIDEBAR_DEFAULT_WIDTH;
    const parsed = JSON.parse(raw) as { sidebar?: number };
    return clampSidebarWidth(parsed.sidebar ?? SIDEBAR_DEFAULT_WIDTH);
  } catch {
    return SIDEBAR_DEFAULT_WIDTH;
  }
}

export function useNavigationSidebar() {
  const pathname = usePathname();
  const user = useAuthStore((state) => state.user);
  const [expanded, setExpandedState] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [width, setWidthState] = useState(SIDEBAR_DEFAULT_WIDTH);
  const [resizing, setResizing] = useState(false);
  const resizeCleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    setExpandedState(readUiPreference("ce.railCollapsed") !== "true");
    setWidthState(readStoredWidth());
  }, []);

  const setExpanded = useCallback((next: boolean) => {
    setExpandedState(next);
    writeUiPreference("ce.railCollapsed", next ? "false" : "true");
  }, []);

  const setWidth = useCallback((next: number) => {
    const clamped = clampSidebarWidth(next);
    setWidthState(clamped);
    writeUiPreference("ce.panelWidths", JSON.stringify({ sidebar: clamped }));
  }, []);

  /* Cmd/Ctrl+K toggles conversation search; Escape closes drawer/search. */
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen((open) => !open);
        return;
      }
      if (event.key === "Escape") {
        setMobileOpen(false);
        setSearchOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => () => resizeCleanupRef.current?.(), []);

  const startResize = useCallback(
    (event: ReactMouseEvent<HTMLDivElement>) => {
      if (!expanded) return;
      event.preventDefault();
      const startX = event.clientX;
      const startWidth = width;
      const previousCursor = document.body.style.cursor;
      const previousUserSelect = document.body.style.userSelect;
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      setResizing(true);

      const onMouseMove = (moveEvent: MouseEvent) => {
        setWidth(startWidth + moveEvent.clientX - startX);
      };
      const cleanup = () => {
        document.body.style.cursor = previousCursor;
        document.body.style.userSelect = previousUserSelect;
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", cleanup);
        resizeCleanupRef.current = null;
        setResizing(false);
      };

      resizeCleanupRef.current?.();
      resizeCleanupRef.current = cleanup;
      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", cleanup);
    },
    [expanded, width, setWidth],
  );

  const items = useMemo(() => {
    const isAdmin = user?.role === "administrator";
    return NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin).map((item) => ({
      ...item,
      active: isRouteActive(pathname, item.href),
    }));
  }, [pathname, user]);

  return {
    pathname,
    expanded,
    items,
    mobileOpen,
    resizing,
    searchOpen,
    width,
    isRouteActive,
    setExpanded,
    setMobileOpen,
    setSearchOpen,
    setWidth,
    startResize,
  };
}
