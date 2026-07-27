"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import type { ReactNode } from "react";
import { PageState } from "@/components/ui/PageState";
import { useAuthStore } from "@/features/auth/auth-store";

const PUBLIC_ROUTES = new Set(["/login"]);

export function AppLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const status = useAuthStore((state) => state.status);
  const isPublic = PUBLIC_ROUTES.has(pathname);

  useEffect(() => {
    if (!isPublic && status === "unauthenticated") {
      router.replace("/login");
    }
    if (pathname === "/login" && status === "authenticated") {
      router.replace("/chat");
    }
  }, [isPublic, pathname, router, status]);

  if (isPublic) return <>{children}</>;

  if (status === "idle" || status === "loading") {
    return <PageState title="Loading" message="Resolving session." />;
  }

  if (status === "unauthenticated") return null;

  return <div className="min-h-screen bg-[var(--bg)] text-[var(--fg)]">{children}</div>;
}
