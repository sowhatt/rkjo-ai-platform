import { NextRequest, NextResponse } from "next/server";
import { backendPilotBearer, isLocalPilotRequest, localEducationApi, pilotEnabled, readPilotSession } from "@/lib/education/studyPilotSession";

export const runtime = "nodejs";

const MAX_BYTES = 15 * 1024 * 1024;

export async function POST(request: NextRequest) {
  // Pilot-only proxy: production must use an integrated authenticated session.
  // No document or bearer token is persisted or logged by this handler.
  if (!pilotEnabled() || !isLocalPilotRequest(request)) {
    return NextResponse.json({ detail: "Pilote désactivé." }, { status: 503 });
  }
  const apiUrl = localEducationApi();
  if (!apiUrl) {
    return NextResponse.json({ detail: "API Education non configurée." }, { status: 503 });
  }
  const session = readPilotSession(request);
  if (!session) {
    return NextResponse.json({ detail: "Connexion étudiant requise." }, { status: 401 });
  }
  const length = Number(request.headers.get("content-length") || 0);
  if (length > MAX_BYTES + 8192) {
    return NextResponse.json({ detail: "PDF trop volumineux." }, { status: 413 });
  }
  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return NextResponse.json({ detail: "Formulaire invalide." }, { status: 400 });
  }
  const file = form.get("file");
  if (!(file instanceof File) || file.type !== "application/pdf" || file.size > MAX_BYTES || file.size === 0) {
    return NextResponse.json({ detail: "PDF valide de 15 Mo maximum requis." }, { status: 400 });
  }
  const programme = form.get("programme_id");
  const ue = form.get("ue_id");
  const type = form.get("document_type");
  if (typeof programme !== "string" || !programme.trim() || programme.length > 120 ||
      typeof ue !== "string" || !ue.trim() || ue.length > 120 ||
      !["cm", "td", "tp"].includes(String(type))) {
    return NextResponse.json({ detail: "Filière, UE et type de cours requis." }, { status: 400 });
  }
  const target = new URL("/education/study/preview-pdf", apiUrl);
  if (!["http:", "https:"].includes(target.protocol)) {
    return NextResponse.json({ detail: "Configuration API invalide." }, { status: 503 });
  }
  try {
    const response = await fetch(target, {
      method: "POST",
      headers: { authorization: backendPilotBearer(session) },
      body: form,
      cache: "no-store",
      signal: AbortSignal.timeout(45000),
    });
    const payload: unknown = await response.json();
    return NextResponse.json(payload, {
      status: response.status,
      headers: { "cache-control": "no-store" },
    });
  } catch {
    return NextResponse.json({ detail: "Service de lecture PDF indisponible." }, { status: 502 });
  }
}
