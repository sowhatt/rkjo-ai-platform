import { NextRequest, NextResponse } from "next/server";

const API_URL =
  process.env.RKJO_API_URL ??
  "http://127.0.0.1:8000";

const API_KEY =
  process.env.RKJO_OPERATOR_API_KEY ?? "";

type RouteContext = {
  params: Promise<{
    courseId: string;
  }>;
};

export async function GET(
  _request: NextRequest,
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

  const { courseId } = await context.params;

  const response = await fetch(
    `${API_URL}/education/courses/${encodeURIComponent(
      courseId,
    )}/assessments`,
    {
      method: "GET",
      headers: {
        "X-API-Key": API_KEY,
      },
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
