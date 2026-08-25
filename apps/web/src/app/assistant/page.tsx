"use client";

import { FormEvent, useState } from "react";

import { askRag } from "@/lib/api";
import type {
  RAGAnswerResponse,
} from "@/lib/types";

export default function AssistantPage() {
  const [question, setQuestion] = useState("");
  const [result, setResult] =
    useState<RAGAnswerResponse | null>(null);
  const [loading, setLoading] =
    useState(false);
  const [error, setError] =
    useState<string | null>(null);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!question.trim()) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await askRag({
        question,
        limit: 5,
      });

      setResult(response);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unexpected error",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl p-8">
      <div className="mb-10">
        <p className="text-sm font-medium text-zinc-500">
          RKJO AI Platform
        </p>

        <h1 className="mt-2 text-3xl font-semibold">
          Assistant RAG
        </h1>

        <p className="mt-3 text-zinc-600">
          Pose une question sur les documents
          indexés dans RKJO.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="space-y-4"
      >
        <textarea
          value={question}
          onChange={(event) =>
            setQuestion(event.target.value)
          }
          placeholder="Pose une question..."
          className="min-h-32 w-full rounded-xl border border-zinc-300 p-4 outline-none focus:border-zinc-900"
        />

        <button
          type="submit"
          disabled={loading}
          className="rounded-xl bg-zinc-900 px-5 py-3 text-white disabled:opacity-50"
        >
          {loading
            ? "Recherche..."
            : "Interroger RKJO"}
        </button>
      </form>

      {error && (
        <div className="mt-8 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">
          {error}
        </div>
      )}

      {result && (
        <section className="mt-10 space-y-8">
          <div>
            <h2 className="text-xl font-semibold">
              Réponse
            </h2>

            <div className="mt-3 whitespace-pre-wrap rounded-xl border border-zinc-200 bg-white p-5">
              {result.answer}
            </div>
          </div>

          <div>
            <h2 className="text-xl font-semibold">
              Sources
            </h2>

            <div className="mt-3 grid gap-3">
              {result.sources.map((source) => (
                <div
                  key={`${source.document_id}-${source.chunk_id}`}
                  className="rounded-xl border border-zinc-200 p-4"
                >
                  <div className="font-medium">
                    [{source.citation}]{" "}
                    {source.document_id}
                  </div>

                  <div className="mt-1 text-sm text-zinc-500">
                    chunk: {source.chunk_id}
                  </div>

                  <div className="mt-1 text-sm text-zinc-500">
                    score:{" "}
                    {source.score.toFixed(4)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
    </main>
  );
}
