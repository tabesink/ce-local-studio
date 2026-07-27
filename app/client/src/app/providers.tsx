"use client";

import { useEffect } from "react";
import type { ReactNode } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppearanceProvider } from "@/features/user-preferences/AppearanceProvider";
import { setUnauthorizedHandler } from "@/lib/api/client";
import { useAuthStore } from "@/features/auth/auth-store";

export function Providers({ children }: { children: ReactNode }) {
  const bootstrap = useAuthStore((state) => state.bootstrap);
  const markUnauthenticated = useAuthStore((state) => state.markUnauthenticated);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      markUnauthenticated();
    });
    void bootstrap();
    return () => setUnauthorizedHandler(null);
  }, [bootstrap, markUnauthenticated]);

  return (
    <AppearanceProvider>
      <AppLayout>{children}</AppLayout>
    </AppearanceProvider>
  );
}
