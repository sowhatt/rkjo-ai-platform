import { relayAuthenticated } from "@/lib/authenticated-proxy";

export async function GET(request: Request) {
  return relayAuthenticated(request, "/education/courses");
}
export async function POST(request: Request) {
  return relayAuthenticated(request, "/education/courses");
}
