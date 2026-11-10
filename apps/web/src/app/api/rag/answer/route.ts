import { relayAuthenticated } from "@/lib/authenticated-proxy";

export async function POST(request: Request) {
  return relayAuthenticated(request, "/rag/answer");
}
