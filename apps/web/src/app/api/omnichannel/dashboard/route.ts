import { GET as proxyGet } from "@/lib/omnichannel-proxy";

export async function GET(request: Request) {
  return proxyGet(request);
}
