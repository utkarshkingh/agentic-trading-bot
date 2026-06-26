/**
 * Resolves the trading backend base URL.
 *
 * Priority:
 *   1. A user-set value in localStorage (used by the Android/packaged app's
 *      settings screen to point at a backend on the LAN or a hosted server).
 *   2. The NEXT_PUBLIC_BACKEND_URL build-time env var.
 *   3. localhost — the default for desktop, where the backend runs as a
 *      bundled sidecar on the same machine.
 */
const DEFAULT_BACKEND_URL = "http://localhost:8000/";
const STORAGE_KEY = "trading.backendUrl";

export function getBackendUrl(): string {
  if (typeof window !== "undefined") {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && stored.trim()) return normalize(stored);
  }
  const fromEnv = process.env.NEXT_PUBLIC_BACKEND_URL;
  return normalize(fromEnv?.trim() || DEFAULT_BACKEND_URL);
}

export function setBackendUrl(url: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, normalize(url));
}

/** Ensure exactly one trailing slash — the AG-UI HttpAgent expects a base URL. */
function normalize(url: string): string {
  return url.endsWith("/") ? url : `${url}/`;
}
