import { NextRequest, NextResponse } from "next/server";
import { audioEstimate, audioPrices, type AudioPlan } from "@/lib/education/audioQuote";
import { isLocalPilotRequest, pilotEnabled, readPilotSession } from "@/lib/education/studyPilotSession";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  if (!pilotEnabled() || !isLocalPilotRequest(request)) {
    return NextResponse.json({ detail: "Pilote indisponible." }, { status: 404 });
  }
  if (!readPilotSession(request)) {
    return NextResponse.json({ detail: "Connexion étudiant requise." }, { status: 401 });
  }
  if (Number(request.headers.get("content-length") || 0) > 1024) {
    return NextResponse.json({ detail: "Requête trop volumineuse." }, { status: 413 });
  }
  let input: unknown;
  try { input = await request.json(); } catch {
    return NextResponse.json({ detail: "Format invalide." }, { status: 400 });
  }
  if (!input || typeof input !== "object") {
    return NextResponse.json({ detail: "Paramètres requis." }, { status: 400 });
  }
  const fields = input as Record<string, unknown>;
  if (typeof fields.minutes !== "number" || typeof fields.plan !== "string" ||
      !Object.prototype.hasOwnProperty.call(audioPrices, fields.plan)) {
    return NextResponse.json({ detail: "Durée et formule requises." }, { status: 400 });
  }
  try {
    const quote = audioEstimate(fields.minutes, fields.plan as AudioPlan);
    return NextResponse.json({
      ...quote,
      detail: "Prix purement indicatif, non contractuel : aucun paiement ou résumé lancé.",
    }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ detail: "Durée comprise entre 1 et 600 minutes requise." }, { status: 400 });
  }
}
