"use client";

import {
  FormEvent,
  useState,
} from "react";

import {
  uploadDocument,
} from "@/lib/api";

type UploadResult = {
  document_id: string;
  content_hash: string;
  chunk_count: number;
  duplicate: boolean;
};

export default function DocumentsPage() {
  const [file, setFile] =
    useState<File | null>(null);

  const [documentId, setDocumentId] =
    useState("");

  const [result, setResult] =
    useState<UploadResult | null>(null);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!file) {
      setError(
        "Sélectionne un document.",
      );
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const formData = new FormData();

      formData.append(
        "file",
        file,
      );

      if (documentId.trim()) {
        formData.append(
          "document_id",
          documentId.trim(),
        );
      }

      formData.append(
        "metadata",
        JSON.stringify({
          source:
            "rkjo-web-console",
        }),
      );

      const response =
        await uploadDocument(
          formData,
        );

      setResult(response);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Erreur inattendue",
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
          Documents
        </h1>

        <p className="mt-3 text-zinc-600">
          Importe un document dans la base
          de connaissance RKJO.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="space-y-5 rounded-xl border border-zinc-200 p-6"
      >
        <div>
          <label className="mb-2 block text-sm font-medium">
            Document
          </label>

          <input
            type="file"
            accept=".pdf,.txt,.md,.markdown"
            onChange={(event) =>
              setFile(
                event.target.files?.[0] ??
                  null,
              )
            }
          />
        </div>

        <div>
          <label className="mb-2 block text-sm font-medium">
            Identifiant
          </label>

          <input
            value={documentId}
            onChange={(event) =>
              setDocumentId(
                event.target.value,
              )
            }
            placeholder="ex: anatomie-coeur"
            className="w-full rounded-xl border border-zinc-300 p-3 outline-none focus:border-zinc-900"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="rounded-xl bg-zinc-900 px-5 py-3 text-white disabled:opacity-50"
        >
          {loading
            ? "Import en cours..."
            : "Importer"}
        </button>
      </form>

      {error && (
        <div className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">
          {error}
        </div>
      )}

      {result && (
        <section className="mt-8 rounded-xl border border-zinc-200 p-6">
          <h2 className="text-xl font-semibold">
            Document indexé
          </h2>

          <dl className="mt-4 space-y-2 text-sm">
            <div>
              <dt className="font-medium">
                document_id
              </dt>
              <dd className="text-zinc-600">
                {result.document_id}
              </dd>
            </div>

            <div>
              <dt className="font-medium">
                chunks
              </dt>
              <dd className="text-zinc-600">
                {result.chunk_count}
              </dd>
            </div>

            <div>
              <dt className="font-medium">
                duplicate
              </dt>
              <dd className="text-zinc-600">
                {String(
                  result.duplicate,
                )}
              </dd>
            </div>
          </dl>
        </section>
      )}
    </main>
  );
}
