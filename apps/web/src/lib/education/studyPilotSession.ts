import { createHmac, randomUUID, timingSafeEqual } from "node:crypto";
import { NextRequest } from "next/server";

export const SESSION_COOKIE = "rkjo_edu_study_pilot";
const MAX_AGE_SECONDS = 1800;

export function pilotEnabled(): boolean {
  return process.env.NODE_ENV === "development" &&
    process.env.RKJO_EDUCATION_STUDY_PILOT === "enabled" &&
    !!process.env.RKJO_EDUCATION_PILOT_PASSWORD &&
    (process.env.RKJO_EDUCATION_PILOT_SESSION_SECRET?.length ?? 0) >= 32 &&
    (process.env.RKJO_JWT_SECRET?.length ?? 0) >= 32;
}

function mac(text: string): string {
  const key = process.env.RKJO_EDUCATION_PILOT_SESSION_SECRET;
  if (!key) throw new Error("Session key unavailable");
  return createHmac("sha256", key).update(text).digest("base64url");
}

function equalStrings(a: string, b: string): boolean {
  const aa = Buffer.from(a);
  const bb = Buffer.from(b);
  return aa.length === bb.length && timingSafeEqual(aa, bb);
}

export function pilotPasswordMatches(value: string): boolean {
  if (!pilotEnabled()) return false;
  return equalStrings(value, process.env.RKJO_EDUCATION_PILOT_PASSWORD ?? "");
}

export function createPilotSession(): string {
  if (!pilotEnabled()) throw new Error("Pilot disabled");
  const payload = Buffer.from(JSON.stringify({
    sub: "etudiant-pilote",
    tenant: "local-education-pilot",
    exp: Math.floor(Date.now() / 1000) + MAX_AGE_SECONDS,
    nonce: randomUUID(),
  })).toString("base64url");
  return `${payload}.${mac(payload)}`;
}

export function readPilotSession(request: NextRequest): { sub: string; tenant: string } | null {
  if (!pilotEnabled()) return null;
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token || token.length > 2048) return null;
  const parts = token.split(".");
  if (parts.length !== 2 || !equalStrings(parts[1], mac(parts[0]))) return null;
  try {
    const data: unknown = JSON.parse(Buffer.from(parts[0], "base64url").toString("utf8"));
    if (!data || typeof data !== "object") return null;
    const obj = data as Record<string, unknown>;
    if (obj.sub !== "etudiant-pilote" || obj.tenant !== "local-education-pilot" ||
      typeof obj.exp !== "number" || obj.exp <= Math.floor(Date.now() / 1000)) return null;
    return { sub: obj.sub, tenant: obj.tenant };
  } catch { return null; }
}

export function backendPilotBearer(session: { sub: string; tenant: string }): string {
  if (!pilotEnabled()) throw new Error("Pilot disabled");
  const now = Math.floor(Date.now() / 1000);
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const payload = Buffer.from(JSON.stringify({
    sub: session.sub, role: "viewer", tenant_id: session.tenant,
    iat: now, exp: now + 60,
  })).toString("base64url");
  const base = `${header}.${payload}`;
  const signature = createHmac("sha256", process.env.RKJO_JWT_SECRET!)
    .update(base).digest("base64url");
  return `Bearer ${base}.${signature}`;
}

export function isLocalPilotRequest(request: NextRequest): boolean {
  const host = request.nextUrl.hostname;
  if (host !== "localhost" && host !== "127.0.0.1") return false;
  const origin = request.headers.get("origin");
  if (!origin) return true;
  try { return new URL(origin).origin === request.nextUrl.origin; }
  catch { return false; }
}

export function localEducationApi(): URL | null {
  const value = process.env.RKJO_EDUCATION_API_URL;
  if (!value) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== "http:" || !["localhost", "127.0.0.1"].includes(url.hostname) ||
      url.username || url.password || url.search || url.hash ||
      (url.pathname !== "/" && url.pathname !== "")) return null;
    return url;
  } catch { return null; }
}

export const pilotCookieOptions = {
  httpOnly: true,
  secure: false,
  sameSite: "strict" as const,
  path: "/",
  maxAge: MAX_AGE_SECONDS,
};
