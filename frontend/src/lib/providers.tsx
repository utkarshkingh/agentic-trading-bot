"use client";

import { HttpAgent } from "@ag-ui/client";
import { CopilotKitProvider } from "@copilotkit/react-core/v2";
import { type ReactNode, useMemo } from "react";

import { tradingCatalog } from "@/lib/a2ui-catalog";
import { getBackendUrl } from "@/lib/config";

/**
 * Connects the UI straight to the FastAPI AG-UI backend via an HttpAgent,
 * with no intermediate Node runtime. This keeps the frontend a pure static
 * bundle (required by Tauri) and removes a server tier — the same build runs
 * as a desktop app talking to a bundled sidecar or as a mobile app talking
 * to a backend over the network.
 */
export function AppProviders({ children }: { children: ReactNode }) {
  const agents = useMemo(
    () => ({ trading_agent: new HttpAgent({ url: getBackendUrl() }) }),
    [],
  );

  return (
    <CopilotKitProvider
      agents__unsafe_dev_only={agents}
      a2ui={{ catalog: tradingCatalog }}
    >
      {children}
    </CopilotKitProvider>
  );
}
