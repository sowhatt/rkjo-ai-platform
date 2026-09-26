const API_URL = process.env.RKJO_API_URL ?? "http://127.0.0.1:8100";
const API_KEY = process.env.RKJO_VIEWER_API_KEY ?? process.env.RKJO_OPERATOR_API_KEY ?? "";

export async function GET(_request: Request, context: { params: Promise<{ learnerId: string }> }) {
  if (!API_KEY) return Response.json({ detail: "RKJO API key is not configured." }, { status: 500 });
  const { learnerId } = await context.params;
  const response = await fetch(`${API_URL}/education/supervision/learners/${encodeURIComponent(learnerId)}/detail`, {
    headers: { "X-API-Key": API_KEY },
    cache: "no-store",
  });
  return new Response(await response.text(), {
    status: response.status,
    headers: { "Content-Type": response.headers.get("content-type") ?? "application/json" },
  });
}
