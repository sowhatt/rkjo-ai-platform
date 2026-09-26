import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.RKJO_API_URL ?? "http://127.0.0.1:8000";
const API_KEY = process.env.RKJO_OPERATOR_API_KEY ?? "";

export async function POST(request: NextRequest) {
  const body = await request.json();
  const response = await fetch(`${API_URL}/education/hints`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
    },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({
    detail: "Réponse API invalide",
  }));
  return NextResponse.json(payload, { status: response.status });
}
