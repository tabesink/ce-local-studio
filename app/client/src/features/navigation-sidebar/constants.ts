export const SIDEBAR_MIN_WIDTH = 188;
export const SIDEBAR_MAX_WIDTH = 320;
export const SIDEBAR_DEFAULT_WIDTH = 224;

export type NavItemDef = {
  href: string;
  label: string;
  icon: "chat" | "library" | "graph" | "settings";
  adminOnly?: boolean;
};

/* Phase 1 nav registry. Logs, Usage, Server, publication, and other
   later-release product surfaces stay unregistered until their contracts are approved. */
export const NAV_ITEMS: NavItemDef[] = [
  { href: "/chat", label: "Chat", icon: "chat" },
  { href: "/documents", label: "Library", icon: "library" },
  { href: "/database-visualize", label: "Graph", icon: "graph" },
];

export const SETTINGS_NAV_ITEM: NavItemDef = {
  href: "/settings",
  label: "Settings",
  icon: "settings",
};
