import { NextResponse } from "next/server";

const API_URL =
  process.env.RKJO_API_URL ??
  "http://127.0.0.1:8000";

const API_KEY =
  process.env.RKJO_OPERATOR_API_KEY ?? "";

export async function POST(
  request: Request,
  context: {
    params: Promise<{
      courseId: string;
    }>;
  },
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

  const { courseId } =
    await context.params;

  const payload = await request.json();

  const response = await fetch(
    `${API_URL}/education/courses/${courseId}/documents`,
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
        response.headers.get(
          "content-type",
        ) ?? "application/json",
    },
  });
}
