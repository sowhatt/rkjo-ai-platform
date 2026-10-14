import { NextRequest, NextResponse } from "next/server";
import { readPilotSession, localEducationApi } from "@/lib/education/studyPilotSession";
import {
  getStudentSession, studentBackendBearer,
} from "@/lib/education/individualStudentSession";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const headers = { "Cache-Control": "no-store" };
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(request: NextRequest) {
  // A shared pilot cookie never becomes a learner identity.
  const identity = getStudentSession(request);
  if (!identity) {
    const shared = readPilotSession(request);
    return NextResponse.json({
      detail: shared
        ? "La session pilote partagée ne donne pas accès au professeur individuel."
        : "Connecte-toi avec le compte étudiant individuel de démonstration.",
    }, { status: shared ? 403 : 401, headers });
  }
  if (Number(request.headers.get("content-length") ?? 0) > 8192) {
    return NextResponse.json({ detail: "Réponse trop longue." }, { status: 413, headers });
  }
  const body: unknown = await request.json().catch(() => null);
  if (!body || typeof body !== "object") {
    return NextResponse.json({ detail: "Requête invalide." }, { status: 400, headers });
  }
  const input = body as Record<string, unknown>;
  const answer = input.student_answer;
  if (![input.course_id, input.assessment_id, input.question_id].every(
    (value) => typeof value === "string" && UUID.test(value),
  ) || typeof answer !== "string" || !answer.trim() || answer.length > 3000) {
    return NextResponse.json({ detail: "Contexte de cours ou réponse invalide." }, { status: 400, headers });
  }
  const api = localEducationApi();
  if (!api) return NextResponse.json({ detail: "API locale indisponible." }, { status: 503, headers });
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(new URL("/education/tutor/feedback", api), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: studentBackendBearer(identity),
        },
        body: JSON.stringify({
          course_id: input.course_id,
          assessment_id: input.assessment_id,
          question_id: input.question_id,
          student_answer: answer,
          help_requested: input.help_requested === true,
        }),
        signal: controller.signal,
        cache: "no-store",
      });
      const result: unknown = await response.json().catch(() => ({}));
      return NextResponse.json(result, { status: response.status, headers });
    } finally {
      clearTimeout(timeout);
    }
  } catch {
    return NextResponse.json({
      detail: "Impossible de joindre le professeur IA local. Vérifie le serveur FastAPI.",
    }, { status: 502, headers });
  }
}
