"use client";

import type { ReactNode } from "react";
import { NavigationSidebar } from "@/features/navigation-sidebar/NavigationSidebar";

/* Local Studio workstation shell: wide resizable sidebar + main canvas.
   Auth gate stays in AppLayout; chat workbench stays in chat-shell. */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-[var(--app-height)] min-h-0 w-full overflow-hidden bg-[var(--ui-bg)] text-[var(--ui-fg)]">
      <NavigationSidebar />
      <main className="min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden bg-[var(--agent-bg)] pt-14 md:pt-0">
        {children}
      </main>
    </div>
  );
}
