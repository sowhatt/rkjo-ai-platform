import { NextRequest, NextResponse } from "next/server";
import { readPilotSession } from "@/lib/education/studyPilotSession";

export const dynamic = "force-dynamic";

const headers = { "Cache-Control": "no-store" };

/**
 * Do not forward the operator key or the shared study-pilot cookie as the
 * identity of a specific learner. FastAPI requires an individually bound,
 * tenant-scoped Bearer subject for formative feedback.
 *
 * Replace this explicit fail-closed gate only when an authenticated
 * account-to-learner resolver can produce an individual backend session.
 */
export async function POST(request: NextRequest) {
  const session = readPilotSession(request);
  if (!session) {
    return NextResponse.json(
      { detail: "Connecte-toi avec un compte étudiant individuel pour recevoir le retour IA." },
      { status: 401, headers },
    );
  }
  return NextResponse.json(
    {
      detail: "Le pilote partagé ne peut pas accéder aux corrections individuelles. " +
        "La connexion sécurisée d'un compte étudiant est nécessaire.",
    },
    { status: 403, headers },
  );
}
