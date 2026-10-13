import { NextRequest, NextResponse } from "next/server";
import { readPilotSession } from "@/lib/education/studyPilotSession";

type Context = {
  params: Promise<{ attemptId: string; questionId: string }>;
};

/**
 * Security gate. The current study pilot cookie represents a shared
 * demonstrator, not a real learner account. It must NEVER be exchanged for
 * a learner-specific Bearer token or an operator API key.
 *
 * Once individual authentication and a tenant-scoped account→learner mapping
 * exist, replace this guard with a server-side session resolver and forward
 * a short-lived identity-bound Bearer token to FastAPI.
 */
export async function GET(request: NextRequest, context: Context) {
  // Resolve route parameters without treating them as authentication.
  await context.params;
  const session = readPilotSession(request);

  if (!session) {
    return NextResponse.json(
      { detail: "Connexion étudiante individuelle requise." },
      { status: 401, headers: { "Cache-Control": "no-store" } },
    );
  }

  // A shared pilot password must not grant learner-specific records.
  return NextResponse.json(
    {
      detail:
        "Next Best Action indisponible sur la session partagée : " +
        "association sécurisée du compte à l'étudiant requise.",
    },
    { status: 403, headers: { "Cache-Control": "no-store" } },
  );
}
