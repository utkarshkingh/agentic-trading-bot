import { handleCopilotSubpathRequest } from "../handler";
import type { NextRequest } from "next/server";

export async function GET(req: NextRequest) {
  return handleCopilotSubpathRequest(req);
}

export async function POST(req: NextRequest) {
  return handleCopilotSubpathRequest(req);
}
