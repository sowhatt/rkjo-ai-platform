import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto min-h-screen max-w-5xl p-10">
      <p className="text-sm font-medium text-zinc-500">
        RKJO AI Platform
      </p>

      <h1 className="mt-3 text-4xl font-semibold">
        AI Platform Console
      </h1>

      <p className="mt-4 max-w-2xl text-zinc-600">
        Pilote les capacités RAG, documents,
        agents et workflows de RKJO depuis
        une interface unique.
      </p>

      <div className="mt-10 grid gap-4 md:grid-cols-3">
        <Link
          href="/assistant"
          className="rounded-xl border p-5 hover:bg-zinc-50"
        >
          <h2 className="font-semibold">
            Assistant
          </h2>
          <p className="mt-2 text-sm text-zinc-500">
            Interroger la connaissance RKJO.
          </p>
        </Link>

        <Link
          href="/documents"
          className="rounded-xl border p-5 hover:bg-zinc-50"
        >
          <h2 className="font-semibold">
            Documents
          </h2>
          <p className="mt-2 text-sm text-zinc-500">
            Gérer les documents et versions.
          </p>
        </Link>

        <Link
          href="/dashboard"
          className="rounded-xl border p-5 hover:bg-zinc-50"
        >
          <h2 className="font-semibold">
            Dashboard
          </h2>
          <p className="mt-2 text-sm text-zinc-500">
            Superviser la plateforme.
          </p>
        </Link>
      </div>
    </main>
  );
}
