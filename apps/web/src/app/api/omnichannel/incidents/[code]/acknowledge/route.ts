import { POST as proxyPost } from "@/lib/omnichannel-proxy";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ code: string }> },
) {
  const { code } = await params;
  return proxyPost(request, code);
}
