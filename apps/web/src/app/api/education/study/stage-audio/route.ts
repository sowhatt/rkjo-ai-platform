import { NextRequest, NextResponse } from "next/server";
import {
  backendPilotBearer, isLocalPilotRequest, localEducationApi,
  pilotEnabled, readPilotSession,
} from "@/lib/education/studyPilotSession";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_BYTES = 50 * 1024 * 1024;

export async function POST(request: NextRequest) {
  if (!pilotEnabled() || !isLocalPilotRequest(request)) {
    return NextResponse.json({ detail: "Pilote audio indisponible." }, { status: 404 });
  }
  const session = readPilotSession(request);
  if (!session) return NextResponse.json({ detail: "Connexion étudiant requise." }, { status: 401 });
  if (process.env.RKJO_EDUCATION_AUDIO_STAGING !== "enabled") {
    return NextResponse.json({ detail: "Stockage pilote désactivé." }, { status: 404 });
  }
  const base = localEducationApi();
  if (!base) return NextResponse.json({ detail: "API Education non configurée." }, { status: 503 });
  if (Number(request.headers.get("content-length") || 0) > MAX_BYTES + 8192) {
    return NextResponse.json({ detail: "Audio trop volumineux." }, { status: 413 });
  }
  let form: FormData;
  try { form = await request.formData(); }
  catch { return NextResponse.json({ detail: "Formulaire invalide." }, { status: 400 }); }
  const file = form.get("file");
  if (!(file instanceof File) || file.size < 1 || file.size > MAX_BYTES ||
      !["audio/wav", "audio/x-wav", "audio/wave"].includes(file.type)) {
    return NextResponse.json({ detail: "Fichier WAV de 50 Mo maximum requis." }, { status: 400 });
  }
  const programme = form.get("programme_id");
  const ue = form.get("ue_id");
  if (typeof programme !== "string" || !programme.trim() || programme.length > 120 ||
      typeof ue !== "string" || !ue.trim() || ue.length > 120) {
    return NextResponse.json({ detail: "Formation et UE requises." }, { status: 400 });
  }
  if (form.get("recording_authorized") !== "true" ||
      form.get("processing_rights_confirmed") !== "true") {
    return NextResponse.json({ detail: "Autorisations requises." }, { status: 422 });
  }
  try {
    const response = await fetch(new URL("/education/study/stage-audio", base), {
      method: "POST",
      headers: { authorization: backendPilotBearer(session) },
      body: form,
      cache: "no-store",
      signal: AbortSignal.timeout(60000),
    });
    const data: unknown = await response.json();
    return NextResponse.json(data, {
      status: response.status,
      headers: { "cache-control": "no-store" },
    });
  } catch {
    return NextResponse.json({ detail: "Inspection audio indisponible." }, { status: 502 });
  }
}
