import { NextResponse } from "next/server";

const API_URL =
  process.env.RKJO_API_URL ??
  "http://127.0.0.1:8000";

const API_KEY =
  process.env.RKJO_VIEWER_API_KEY ?? "";

export async function POST(
  request: Request,
) {
  if (!API_KEY) {
    return NextResponse.json(
      {
        detail:
          "RKJO viewer API key is not configured.",
      },
      {
        status: 500,
      },
    );
  }

  const payload = await request.json();

  const response = await fetch(
    `${API_URL}/rag/answer`,
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
