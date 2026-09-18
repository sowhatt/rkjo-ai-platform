import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.RKJO_API_URL ?? "http://127.0.0.1:8000";
const API_KEY = process.env.RKJO_OPERATOR_API_KEY ?? "";

type RouteContext = {
  params: Promise<{
    learnerId: string;
    courseId: string;
  }>;
};

export async function GET(
  _request: NextRequest,
  context: RouteContext,
) {
  const { learnerId, courseId } = await context.params;

  const response = await fetch(
    `${API_URL}/education/learners/${encodeURIComponent(
      learnerId,
    )}/courses/${encodeURIComponent(courseId)}/progress`,
    {
      headers: {
        "X-API-Key": API_KEY,
      },
      cache: "no-store",
    },
  );

  const payload = await response.json().catch(() => ({
    detail: "Réponse API invalide",
  }));

  return NextResponse.json(payload, {
    status: response.status,
  });
}
