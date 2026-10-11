/** OMNI-016.4.2: authenticated, no-cache browser-to-RKJO API proxy.
 * A caller must supply its own tenant-bound bearer identity. Never use a
 * shared server API key here: doing so would grant anonymous cockpit access.
 */
import { NextResponse } from "next/server";

const API_URL = process.env.RKJO_API_URL ?? "http://127.0.0.1:8000";

async function relay(request: Request, method: "GET" | "POST", code?: string) {
  const authorization = request.headers.get("authorization") ?? "";
  if (!/^Bearer [^\s]+$/.test(authorization)) {
    return NextResponse.json({ detail: "Bearer token required." }, { status: 401 });
  }
  if (code && !/^[A-Z][A-Z0-9_]{0,127}$/.test(code)) {
    return NextResponse.json({ detail: "Invalid incident code." }, { status: 422 });
  }
  const path = code
    ? `/omnichannel/incidents/${encodeURIComponent(code)}/acknowledge`
    : "/omnichannel/dashboard";
  try {
    const upstream = await fetch(`${API_URL}${path}`, {
      method,
      headers: { Authorization: authorization, Accept: "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    const body = await upstream.text();
    // Do not echo upstream HTML, redirects, cookies, or unsafe headers.
    if (body.length > 1_000_000) {
      return NextResponse.json({ detail: "Upstream response too large." }, { status: 502 });
    }
    if (!(upstream.headers.get("content-type") ?? "").includes("application/json")) {
      return NextResponse.json({ detail: "Invalid upstream response." }, { status: 502 });
    }
    return new Response(body, {
      status: upstream.status,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch {
    return NextResponse.json({ detail: "RKJO API unavailable." }, { status: 503 });
  }
}

export async function GET(request: Request) {
  return relay(request, "GET");
}

export async function POST(request: Request, code: string) {
  return relay(request, "POST", code);
}
