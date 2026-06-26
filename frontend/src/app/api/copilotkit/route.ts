import { handleCopilotRequest } from "./handler";
import type { NextRequest } from "next/server";

export async function GET(req: NextRequest) {
  return handleCopilotRequest(req);
}

export async function POST(req: NextRequest) {
  return handleCopilotRequest(req);
}
