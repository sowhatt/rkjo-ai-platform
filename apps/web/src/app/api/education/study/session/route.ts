import { NextRequest, NextResponse } from "next/server";
import {
  SESSION_COOKIE, createPilotSession, isLocalPilotRequest, pilotCookieOptions,
  pilotEnabled, pilotPasswordMatches, readPilotSession,
} from "@/lib/education/studyPilotSession";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const noStore = { "cache-control": "no-store" };

export async function GET(request: NextRequest) {
  if (!pilotEnabled() || !isLocalPilotRequest(request)) {
    return NextResponse.json({ detail: "Pilote indisponible." }, { status: 404, headers: noStore });
  }
  return NextResponse.json(
    { connected: readPilotSession(request) !== null },
    { headers: noStore },
  );
}

export async function POST(request: NextRequest) {
  if (!pilotEnabled() || !isLocalPilotRequest(request)) {
    return NextResponse.json({ detail: "Pilote indisponible." }, { status: 404, headers: noStore });
  }
  if (Number(request.headers.get("content-length") ?? 0) > 2048) {
    return NextResponse.json({ detail: "Requête trop volumineuse." }, { status: 413, headers: noStore });
  }
  let body: unknown;
  try { body = await request.json(); }
  catch { return NextResponse.json({ detail: "Requête invalide." }, { status: 400, headers: noStore }); }
  if (!body || typeof body !== "object" || !("password" in body) ||
    typeof body.password !== "string" || body.password.length > 256 ||
    !pilotPasswordMatches(body.password)) {
    return NextResponse.json({ detail: "Code de démonstration incorrect." }, { status: 401, headers: noStore });
  }
  const response = NextResponse.json({ connected: true }, { headers: noStore });
  response.cookies.set(SESSION_COOKIE, createPilotSession(), pilotCookieOptions);
  return response;
}

export async function DELETE(request: NextRequest) {
  if (!pilotEnabled() || !isLocalPilotRequest(request)) {
    return NextResponse.json({ detail: "Pilote indisponible." }, { status: 404, headers: noStore });
  }
  const response = NextResponse.json({ connected: false }, { headers: noStore });
  response.cookies.set(SESSION_COOKIE, "", { ...pilotCookieOptions, maxAge: 0 });
  return response;
}
