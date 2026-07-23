import type { Metadata } from "next";
import { Providers } from "@/app/providers";
import { getAppearanceBootstrapScript } from "@/features/user-preferences/appearanceBootstrap";
import "./globals.css";

export const metadata: Metadata = {
  title: "Context Engine",
  description: "Context Engine frontend delivery foundation.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="zai-dark" data-density="compact" suppressHydrationWarning>
      <head>
        <script
          // Pre-paint appearance apply — sole owner with appearanceRuntime (R4).
          dangerouslySetInnerHTML={{ __html: getAppearanceBootstrapScript() }}
        />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
