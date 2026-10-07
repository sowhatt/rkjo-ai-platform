import { NextRequest, NextResponse } from "next/server";
const API_URL = process.env.RKJO_API_URL ?? "http://127.0.0.1:8100";
const API_KEY = process.env.RKJO_OPERATOR_API_KEY ?? "";
export async function GET(request: NextRequest, context: { params: Promise<{ learnerId: string }> }) {
  const { learnerId } = await context.params;
  const response = await fetch(`${API_URL}/education/learners/${learnerId}/today`, {
    headers: { "X-API-Key": API_KEY }, cache: "no-store",
  });
  const payload = await response.json().catch(() => ({ detail: "Réponse API invalide" }));
  return NextResponse.json(payload, { status: response.status });
}
