const API_URL = process.env.RKJO_API_URL ?? "http://127.0.0.1:8100";
const API_KEY = process.env.RKJO_OPERATOR_API_KEY ?? "";

async function forward(learnerId: string, init?: RequestInit) {
  if (!API_KEY) return Response.json({ detail: "RKJO operator API key is not configured." }, { status: 500 });
  const response = await fetch(`${API_URL}/education/supervision/learners/${encodeURIComponent(learnerId)}/interventions`, {
    ...init,
    headers: { "X-API-Key": API_KEY, "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  return new Response(await response.text(), { status: response.status, headers: { "Content-Type": response.headers.get("content-type") ?? "application/json" } });
}

export async function GET(_request: Request, context: { params: Promise<{ learnerId: string }> }) {
  const { learnerId } = await context.params;
  return forward(learnerId);
}

export async function POST(request: Request, context: { params: Promise<{ learnerId: string }> }) {
  const { learnerId } = await context.params;
  return forward(learnerId, { method: "POST", body: await request.text() });
}
