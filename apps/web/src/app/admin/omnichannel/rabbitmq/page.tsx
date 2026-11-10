"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

type Queue = {
  name: string; ready: number; unacked: number; consumers: number;
  total: number; is_dlq: boolean;
};
type Alert = { code: string; severity: string; queue: string; count: number };
type Snapshot = {
  scope: "infrastructure"; evaluated_at: string; healthy: boolean;
  queues: Queue[]; totals: { ready: number; unacked: number; dlq: number };
  alerts: Alert[];
};

export default function RabbitMQAdmin() {
  const [token, setToken] = useState("");
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [auto, setAuto] = useState(false);

  const load = useCallback(async (bearer: string) => {
    if (!bearer.trim()) return;
    setRefreshing(true);
    try {
      const response = await fetch("/api/internal/omnichannel/rabbitmq", {
        headers: { Authorization: `Bearer ${bearer.trim()}` }, cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(response.status === 403 ?
          "Accès réservé aux administrateurs de l'infrastructure." :
          response.status === 401 ? "Jeton invalide ou expiré." :
          "Supervision RabbitMQ indisponible.");
      }
      const result = (await response.json()) as Snapshot;
      if (result.scope !== "infrastructure" || !Array.isArray(result.queues) ||
          !Array.isArray(result.alerts) || !result.totals) {
        throw new Error("Réponse de supervision invalide.");
      }
      setSnapshot(result);
      setError("");
    } catch (cause) {
      setSnapshot(null);
      setError(cause instanceof Error ? cause.message : "Erreur inconnue.");
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (!auto || !token) return;
    const interval = setInterval(() => {
      if (document.visibilityState === "visible") void load(token);
    }, 30000);
    return () => clearInterval(interval);
  }, [auto, token, load]);

  return <main className="min-h-screen bg-slate-50 p-5 text-slate-900 md:p-10">
    <div className="mx-auto max-w-6xl space-y-6">
      <header>
        <Link href="/dashboard" className="text-sm text-blue-800 hover:underline">← Tableau de bord</Link>
        <p className="mt-4 text-xs font-semibold uppercase tracking-widest text-blue-800">
          RKJO · Administration infrastructure</p>
        <h1 className="mt-2 text-3xl font-bold">Supervision RabbitMQ</h1>
        <p className="mt-2 text-sm text-slate-600">
          Données globales des files autorisées. Accès interdit aux comptes tenant.
        </p>
      </header>

      <section className="rounded-2xl border bg-white p-5 shadow-sm">
        <label htmlFor="infra-token" className="text-sm font-semibold">JWT administrateur infrastructure</label>
        <p className="mt-1 text-xs text-slate-500">
          Jeton conservé dans la mémoire de cette page uniquement. Aucune clé API partagée.
        </p>
        <div className="mt-3 flex flex-wrap gap-3">
          <input id="infra-token" type="password" autoComplete="off" value={token}
            onChange={event => { setToken(event.target.value); setSnapshot(null); }}
            className="min-w-0 flex-1 rounded-xl border border-slate-300 p-3"
            placeholder="Coller le JWT de supervision" />
          <button type="button" disabled={!token.trim() || refreshing} onClick={() => void load(token)}
            className="rounded-xl bg-blue-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">
            {refreshing ? "Chargement…" : "Actualiser"}
          </button>
          <button type="button" onClick={() => { setToken(""); setAuto(false); setSnapshot(null); setError(""); }}
            className="rounded-xl border px-4 py-2 text-sm">Déconnecter</button>
        </div>
        <label className="mt-3 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={auto} onChange={event => setAuto(event.target.checked)} />
          Actualisation toutes les 30 secondes, onglet visible uniquement
        </label>
      </section>

      {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
        {error}</div>}
      {!snapshot && !error && <p className="rounded-xl border border-dashed bg-white p-8 text-center text-slate-500">
        Authentifie-toi pour consulter les métriques réelles du broker.</p>}

      {snapshot && <>
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
          <span className={snapshot.healthy ? "font-semibold text-emerald-700" : "font-semibold text-red-700"}>
            {snapshot.healthy ? "Aucune anomalie détectée" : "Anomalies détectées"}</span>
          <span className="text-slate-500">Mesure : {new Date(snapshot.evaluated_at).toLocaleString("fr-FR")}</span>
        </div>
        <section className="grid gap-4 sm:grid-cols-3">
          {([["Prêts", snapshot.totals.ready], ["Non acquittés", snapshot.totals.unacked],
             ["Messages DLQ", snapshot.totals.dlq]] as const).map(([name, value]) =>
            <article key={name} className="rounded-2xl border bg-white p-5 shadow-sm">
              <p className="text-sm text-slate-500">{name}</p>
              <p className="mt-2 text-3xl font-bold tabular-nums">{value.toLocaleString("fr-FR")}</p>
            </article>)}
        </section>
        <section className="rounded-2xl border bg-white p-5 shadow-sm">
          <h2 className="text-xl font-bold">Alertes actives ({snapshot.alerts.length})</h2>
          <div className="mt-3 space-y-2">
            {snapshot.alerts.length === 0 && <p className="text-sm text-slate-500">Aucune alerte selon les seuils configurés.</p>}
            {snapshot.alerts.map((alert, i) =>
              <div key={alert.queue + alert.code + i} className="flex flex-wrap justify-between gap-3 rounded-xl border p-3 text-sm">
                <span><strong>{alert.code}</strong> · {alert.queue}</span>
                <span className={alert.severity === "critical" ? "text-red-700" : "text-amber-700"}>
                  {alert.severity} · {alert.count}</span>
              </div>)}
          </div>
        </section>
        <section className="overflow-x-auto rounded-2xl border bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-xl font-bold">Files supervisées</h2>
          <table className="w-full min-w-xl text-left text-sm">
            <thead><tr className="border-b text-slate-500">
              <th className="p-3">File</th><th className="p-3">Prêts</th>
              <th className="p-3">Non acquittés</th><th className="p-3">Consommateurs</th>
              <th className="p-3">Total</th></tr></thead>
            <tbody>{snapshot.queues.map(queue =>
              <tr key={queue.name} className="border-b last:border-0">
                <td className="p-3 font-medium">{queue.name}{queue.is_dlq ? " · DLQ" : ""}</td>
                <td className="p-3 tabular-nums">{queue.ready}</td>
                <td className="p-3 tabular-nums">{queue.unacked}</td>
                <td className="p-3 tabular-nums">{queue.consumers}</td>
                <td className="p-3 tabular-nums">{queue.total}</td>
              </tr>)}</tbody>
          </table>
        </section>
      </>}
    </div>
  </main>;
}
