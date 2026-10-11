import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Only an explicitly enabled local development relay. No production credentials,
// no cookies, no operator key, and no arbitrary upstream URL.
async function relay(
  request: NextRequest,
  context: { params: Promise<{ segments: string[] }> },
) {
  if (process.env.NODE_ENV !== "development" || process.env.RKJO_CE1_PILOT_WEB_ENABLED !== "1") {
    return NextResponse.json({ detail: "Local CE1 pilot is disabled." }, { status: 404 });
  }
  const upstream = process.env.RKJO_CE1_PILOT_API_URL || "http://127.0.0.1:8000";
  let base: URL;
  try {
    base = new URL(upstream);
  } catch {
    return NextResponse.json({ detail: "Invalid pilot API configuration." }, { status: 503 });
  }
  if (
    base.protocol !== "http:" ||
    !["127.0.0.1", "localhost"].includes(base.hostname) ||
    base.username || base.password || base.pathname !== "/" || base.search || base.hash
  ) {
    return NextResponse.json({ detail: "Pilot API must be local HTTP." }, { status: 503 });
  }
  const auth = request.headers.get("authorization") || "";
  if (!/^Bearer [^\s]+$/.test(auth)) {
    return NextResponse.json({ detail: "Individual Bearer token required." }, { status: 401 });
  }
  const { segments } = await context.params;
  if (
    segments.length < 1 || segments.length > 2 ||
    segments.some((segment) => !/^[a-zA-Z0-9-]+$/.test(segment))
  ) {
    return NextResponse.json({ detail: "Unsupported CE1 route." }, { status: 404 });
  }
  const [session, operation] = segments;
  const sessionOk = /^[0-9a-fA-F-]{36}$/.test(session);
  const allowed = (session === "sessions" && !operation && request.method === "POST") ||
    (sessionOk && operation === "state" && request.method === "GET") ||
    (sessionOk && operation === "teacher-state" && request.method === "GET") ||
    (sessionOk && operation === "commands" && request.method === "POST") ||
    (sessionOk && operation === "turns" && request.method === "POST");
  if (!allowed) {
    return NextResponse.json({ detail: "Unsupported CE1 action." }, { status: 404 });
  }
  const path = session === "sessions"
    ? "/education/ce1-sessions"
    : `/education/ce1-sessions/${session}/${operation}`;
  try {
    const body = request.method === "POST" ? await request.text() : undefined;
    if (body && body.length > 4096) {
      return NextResponse.json({ detail: "Request too large." }, { status: 413 });
    }
    const response = await fetch(new URL(path, base), {
      method: request.method,
      headers: {
        Authorization: auth,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    const text = await response.text();
    return new NextResponse(text, {
      status: response.status,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json({ detail: "Local pilot API unavailable." }, { status: 502 });
  }
}

export async function GET(request: NextRequest, context: { params: Promise<{ segments: string[] }> }) {
  return relay(request, context);
}

export async function POST(request: NextRequest, context: { params: Promise<{ segments: string[] }> }) {
  return relay(request, context);
}
