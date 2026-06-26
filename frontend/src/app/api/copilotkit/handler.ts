import { HttpAgent } from "@ag-ui/client";
import {
  CopilotRuntime,
  InMemoryAgentRunner,
  createCopilotRuntimeHandler,
} from "@copilotkit/runtime/v2";
import { NextRequest } from "next/server";

const BACKEND_URL = process.env.TRADING_BACKEND_URL?.trim() || "http://localhost:8000/";

const runner = new InMemoryAgentRunner();

function buildRuntime() {
  const agent = new HttpAgent({ url: BACKEND_URL });

  return new CopilotRuntime({
    runner,
    agents: { trading_agent: agent },
    a2ui: { injectA2UITool: true },
  });
}

export async function handleCopilotRequest(req: NextRequest) {
  return createCopilotRuntimeHandler({
    runtime: buildRuntime(),
    basePath: "/api/copilotkit",
    mode: "single-route",
  })(req);
}

export async function handleCopilotSubpathRequest(req: NextRequest) {
  return createCopilotRuntimeHandler({
    runtime: buildRuntime(),
    basePath: "/api/copilotkit",
    mode: "multi-route",
  })(req);
}
