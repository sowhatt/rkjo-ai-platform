const API_URL = process.env.RKJO_API_URL ?? "http://127.0.0.1:8000";
const API_KEY = process.env.RKJO_VIEWER_API_KEY ?? process.env.RKJO_OPERATOR_API_KEY ?? "";

export async function GET() {
  if (!API_KEY) return Response.json({ detail: "RKJO API key is not configured." }, { status: 500 });
  const response = await fetch(`${API_URL}/education/supervision/stream`, {
    headers: { "X-API-Key": API_KEY, Accept: "text/event-stream" },
    cache: "no-store",
  });
  if (!response.ok || !response.body) {
    return new Response(await response.text(), { status: response.status });
  }
  return new Response(response.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
}
