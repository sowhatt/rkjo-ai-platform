import type {
  RAGAnswerRequest,
  RAGAnswerResponse,
} from "@/lib/types";

export async function askRag(
  payload: RAGAnswerRequest,
): Promise<RAGAnswerResponse> {
  const response = await fetch(
    "/api/rag/answer",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    const body = await response.text();

    throw new Error(
      body ||
        `RKJO API error: ${response.status}`,
    );
  }

  return response.json();
}

export async function uploadDocument(
  formData: FormData,
) {
  const response = await fetch(
    "/api/rag/documents",
    {
      method: "POST",
      body: formData,
    },
  );

  if (!response.ok) {
    const body = await response.text();

    throw new Error(
      body ||
        `RKJO API error: ${response.status}`,
    );
  }

  return response.json();
}
