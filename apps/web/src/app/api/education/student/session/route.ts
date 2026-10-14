import { NextRequest, NextResponse } from "next/server";
import {
  STUDENT_COOKIE, checkStudentPassword, getStudentSession, issueStudentCookie,
  studentCookieOptions, studentDemoAllowed,
} from "@/lib/education/individualStudentSession";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const headers = { "Cache-Control": "no-store" };

export async function GET(request: NextRequest) {
  if (!studentDemoAllowed(request)) return NextResponse.json({ connected: false }, { status: 404, headers });
  return NextResponse.json({ connected: getStudentSession(request) !== null }, { headers });
}

export async function POST(request: NextRequest) {
  if (!studentDemoAllowed(request)) return NextResponse.json({ detail: "Démonstration étudiante indisponible." }, { status: 404, headers });
  if (Number(request.headers.get("content-length") ?? 0) > 2048) {
    return NextResponse.json({ detail: "Requête trop volumineuse." }, { status: 413, headers });
  }
  const body: unknown = await request.json().catch(() => null);
  if (!body || typeof body !== "object" || !("password" in body) ||
      typeof body.password !== "string" || body.password.length > 256 ||
      !checkStudentPassword(body.password)) {
    return NextResponse.json({ detail: "Code étudiant incorrect." }, { status: 401, headers });
  }
  const response = NextResponse.json({ connected: true }, { headers });
  response.cookies.set(STUDENT_COOKIE, issueStudentCookie(), studentCookieOptions);
  return response;
}

export async function DELETE(request: NextRequest) {
  if (!studentDemoAllowed(request)) return NextResponse.json({ connected: false }, { status: 404, headers });
  const response = NextResponse.json({ connected: false }, { headers });
  response.cookies.set(STUDENT_COOKIE, "", { ...studentCookieOptions, maxAge: 0 });
  return response;
}
