import { NextResponse } from "next/server";

/** Infrastructure-only proxy: never use shared server credentials. */
export async function GET(request: Request) {
  const authorization = request.headers.get("authorization") ?? "";
  if (!/^Bearer [^\s]+$/.test(authorization)) {
    return NextResponse.json({ detail: "Bearer token required." }, { status: 401 });
  }
  const base = process.env.RKJO_API_URL ?? "http://127.0.0.1:8000";
  try {
    const response = await fetch(`${base}/internal/omnichannel/rabbitmq`, {
      headers: { Authorization: authorization, Accept: "application/json" },
      redirect: "manual",
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    });
    const body = await response.text();
    if (body.length > 100000 || !(response.headers.get("content-type") ?? "").includes("application/json") ||
        response.status < 200 || response.status >= 500) {
      return NextResponse.json({ detail: "Broker monitoring unavailable." }, { status: 503 });
    }
    return new Response(body, {
      status: response.status,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
                 "X-Content-Type-Options": "nosniff" },
    });
  } catch {
    return NextResponse.json({ detail: "Broker monitoring unavailable." }, { status: 503 });
  }
}
