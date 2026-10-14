import { createHmac, timingSafeEqual } from "node:crypto";
import { NextRequest } from "next/server";
import { isLocalPilotRequest, localEducationApi } from "@/lib/education/studyPilotSession";

export const STUDENT_COOKIE = "rkjo_edu_individual_student";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const TTL_SECONDS = 1800;

export function studentDemoConfigured(): boolean {
  return process.env.NODE_ENV === "development" &&
    process.env.RKJO_EDUCATION_INDIVIDUAL_DEMO === "enabled" &&
    !!process.env.RKJO_EDUCATION_STUDENT_PASSWORD &&
    UUID.test(process.env.RKJO_EDUCATION_STUDENT_ID ?? "") &&
    UUID.test(process.env.RKJO_EDUCATION_STUDENT_TENANT_ID ?? "") &&
    (process.env.RKJO_EDUCATION_STUDENT_SESSION_SECRET?.length ?? 0) >= 32 &&
    (process.env.RKJO_JWT_SECRET?.length ?? 0) >= 32 &&
    localEducationApi() !== null;
}

export function studentDemoAllowed(request: NextRequest): boolean {
  return studentDemoConfigured() && isLocalPilotRequest(request);
}

function hmac(value: string): string {
  return createHmac("sha256", process.env.RKJO_EDUCATION_STUDENT_SESSION_SECRET!)
    .update(value).digest("base64url");
}

function constantEqual(a: string, b: string): boolean {
  const x = Buffer.from(a);
  const y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
}

export function checkStudentPassword(password: string): boolean {
  return studentDemoConfigured() &&
    constantEqual(password, process.env.RKJO_EDUCATION_STUDENT_PASSWORD ?? "");
}

export type StudentIdentity = { learnerId: string; tenantId: string };

export function issueStudentCookie(): string {
  if (!studentDemoConfigured()) throw new Error("Individual demo not configured");
  const payload = Buffer.from(JSON.stringify({
    learnerId: process.env.RKJO_EDUCATION_STUDENT_ID,
    tenantId: process.env.RKJO_EDUCATION_STUDENT_TENANT_ID,
    exp: Math.floor(Date.now() / 1000) + TTL_SECONDS,
  })).toString("base64url");
  return `${payload}.${hmac(payload)}`;
}

export function getStudentSession(request: NextRequest): StudentIdentity | null {
  if (!studentDemoAllowed(request)) return null;
  const raw = request.cookies.get(STUDENT_COOKIE)?.value;
  if (!raw || raw.length > 2048) return null;
  const parts = raw.split(".");
  if (parts.length !== 2 || !constantEqual(hmac(parts[0]), parts[1])) return null;
  try {
    const obj = JSON.parse(Buffer.from(parts[0], "base64url").toString("utf8")) as Record<string, unknown>;
    if (obj.learnerId !== process.env.RKJO_EDUCATION_STUDENT_ID ||
        obj.tenantId !== process.env.RKJO_EDUCATION_STUDENT_TENANT_ID ||
        typeof obj.exp !== "number" || obj.exp <= Math.floor(Date.now() / 1000)) return null;
    return { learnerId: String(obj.learnerId), tenantId: String(obj.tenantId) };
  } catch { return null; }
}

export function studentBackendBearer(identity: StudentIdentity): string {
  if (!studentDemoConfigured()) throw new Error("Individual demo not configured");
  const now = Math.floor(Date.now() / 1000);
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const payload = Buffer.from(JSON.stringify({
    sub: identity.learnerId, role: "viewer", tenant_id: identity.tenantId,
    iat: now, exp: now + 60,
  })).toString("base64url");
  const input = `${header}.${payload}`;
  const signature = createHmac("sha256", process.env.RKJO_JWT_SECRET!)
    .update(input).digest("base64url");
  return `Bearer ${input}.${signature}`;
}

export const studentCookieOptions = {
  httpOnly: true,
  sameSite: "strict" as const,
  secure: false,
  path: "/",
  maxAge: TTL_SECONDS,
};
