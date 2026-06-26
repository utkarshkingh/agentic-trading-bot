"use client";

import { CopilotKitProvider } from "@copilotkit/react-core/v2";
import type { ReactNode } from "react";

import { tradingCatalog } from "@/lib/a2ui-catalog";

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <CopilotKitProvider
      runtimeUrl="/api/copilotkit"
      a2ui={{ catalog: tradingCatalog }}
    >
      {children}
    </CopilotKitProvider>
  );
}
