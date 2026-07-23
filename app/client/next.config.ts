import type { NextConfig } from "next";

// API proxying lives in src/middleware.ts, not here: next.config.ts rewrites()
// resolves once at `next build` time and is baked into
// .next/routes-manifest.json, so it cannot react to a runtime-supplied
// CONTEXT_ENGINE_API_BASE (e.g. a Docker `-e` flag or compose environment
// value). Middleware runs per-request in the Node.js runtime and reads
// process.env at request time.
const nextConfig: NextConfig = {
  // Next 16 builds with Turbopack by default; an empty turbopack config
  // acknowledges that the webpack() block below is dev/webpack-only so the
  // build does not fail with "webpack config and no turbopack config".
  turbopack: {},
  // pdf.js (Library PDF preview) is ESM; transpile for Next bundling.
  transpilePackages: ["pdfjs-dist"],
  webpack(config, { dev }) {
    // pdfjs-dist optionally references node-canvas; not used in the browser viewer.
    config.resolve.alias = {
      ...config.resolve.alias,
      canvas: false,
    };
    if (dev) {
      config.watchOptions = {
        poll: 1000,
        aggregateTimeout: 300,
        ignored: ["**/.git/**", "**/node_modules/**", "**/.next/**"],
      };
    }
    return config;
  },
};

export default nextConfig;
