import { NextRequest, NextResponse } from "next/server";

const API_URL =
  process.env.RKJO_API_URL ??
  "http://127.0.0.1:8000";

const API_KEY =
  process.env.RKJO_OPERATOR_API_KEY ?? "";

type RouteContext = {
  params: Promise<{
    challengeId: string;
  }>;
};

export async function POST(
  request: NextRequest,
  context: RouteContext,
) {
  if (!API_KEY) {
    return NextResponse.json(
      {
        detail:
          "RKJO operator API key is not configured.",
      },
      {
        status: 500,
      },
    );
  }

  const { challengeId } = await context.params;
  const payload = await request.json();

  const response = await fetch(
    `${API_URL}/education/proof-challenges/${encodeURIComponent(
      challengeId,
    )}/submit`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
      },
      body: JSON.stringify(payload),
      cache: "no-store",
    },
  );

  const body = await response.text();

  return new Response(body, {
    status: response.status,
    headers: {
      "Content-Type":
        response.headers.get("content-type") ??
        "application/json",
    },
  });
}
