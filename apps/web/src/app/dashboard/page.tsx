import Link from "next/link";

export default function DashboardPage() {
  return (
    <main className="p-8">
      <h1 className="text-3xl font-semibold">RKJO Dashboard</h1>
      <p className="mt-3 text-zinc-600">Vue d'ensemble de la plateforme.</p>
      <section className="mt-8 max-w-xl rounded-2xl border border-slate-200 bg-white p-6 text-slate-900">
        <h2 className="text-xl font-semibold">Centre de supervision Omnichannel</h2>
        <p className="mt-2 text-sm text-slate-600">
          Files entrantes, routage, livraisons, alertes et incidents par tenant.
        </p>
        <Link href="/omnichannel" className="mt-4 inline-block rounded-lg bg-blue-800 px-4 py-2 text-sm font-semibold text-white">
          Ouvrir le cockpit →
        </Link>
      </section>
    </main>
  );
}
