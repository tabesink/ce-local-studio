import path from "node:path";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    include: [
      "tests/parity/react/**/*.test.tsx",
      "tests/chat-inspector.test.tsx",
      "tests/documentsDeepLink.test.ts",
    ],
    setupFiles: ["tests/parity/react/setup.ts"],
  },
});
