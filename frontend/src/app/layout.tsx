import "@copilotkit/react-core/v2/styles.css";
import "@copilotkit/react-ui/styles.css";
import "./globals.css";

import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppProviders } from "@/lib/providers";

export const metadata: Metadata = {
  title: "Agentic Trading Bot",
  description: "AI-powered trading analysis with LangGraph multi-agent architecture",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
