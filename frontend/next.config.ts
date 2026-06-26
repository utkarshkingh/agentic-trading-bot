import type { NextConfig } from "next";

/**
 * Static export so the UI can be embedded in a Tauri app (desktop + Android).
 * Tauri serves the prebuilt files from `out/` — there is no Node server at
 * runtime, so all backend calls go to the FastAPI AG-UI backend over HTTP.
 */
const nextConfig: NextConfig = {
  output: "export",
  reactStrictMode: true,
  // Next's image optimizer needs a server; disable it for static export.
  images: { unoptimized: true },
  // Tauri's asset protocol serves from a directory, so emit `path/index.html`.
  trailingSlash: true,
};

export default nextConfig;
