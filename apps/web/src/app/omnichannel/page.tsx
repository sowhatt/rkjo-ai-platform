"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

type QueueHealth = { pending: number; failed: number; expired_leases: number };
type Alert = { code: string; severity: "warning" | "critical"; count: number };
type Incident = {
  code: string; severity: "warning" | "critical";
  status: "open" | "acknowledged" | "resolved";
  count: number; last_seen_at: string; acknowledged_at: string | null;
};
type Dashboard = {
  tenant_id: string; evaluated_at: string; healthy: boolean;
  queues: { inbound: QueueHealth; routes: QueueHealth; outbound: QueueHealth };
  delivery: {
    uncertain_outbound: number; provider_confirmed_uncommitted: number;
    sent_without_binding: number; delivery_receipts: number;
  };
  alerts: Alert[]; incidents: Incident[];
  workers: { name: string; status: string; stale: boolean; last_seen_at: string }[];
};

const labels: Record<string, string> = {
  INBOUND_BACKLOG: "File entrante encombrée",
  ROUTE_BACKLOG: "Routage en attente",
  OUTBOUND_BACKLOG: "Livraison en attente",
  INBOUND_FAILED: "Échecs entrants",
  ROUTE_FAILED: "Échecs de routage",
  OUTBOUND_FAILED: "Échecs de livraison",
  INBOUND_EXPIRED_LEASE: "Lease entrant expiré",
  ROUTE_EXPIRED_LEASE: "Lease de routage expiré",
  OUTBOUND_EXPIRED_LEASE: "Lease sortant expiré",
  UNCERTAIN_OUTBOUND: "Envois incertains",
  PROVIDER_CONFIRMED_UNCOMMITTED: "Preuves à réconcilier",
  SENT_WITHOUT_BINDING: "Envois sans preuve",
};

function label(code: string) {
  return labels[code] ?? code.replaceAll("_", " ");
}

function formatDate(value: string) {
  const timestamp = new Date(value);
  return Number.isNaN(timestamp.getTime()) ? "—" : timestamp.toLocaleString("fr-FR");
}

export default function OmnichannelPage() {
  const [token, setToken] = useState("");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(false);
  const [busyCode, setBusyCode] = useState<string | null>(null);
  const [error, setError] = useState("");
  const tokenRef = useRef(token);
  tokenRef.current = token;
  const [autoRefresh, setAutoRefresh] = useState(false);

  const load = useCallback(async (bearer: string) => {
    if (!bearer.trim()) {
      setDashboard(null);
      setError("Un jeton d'accès tenant-bound est requis.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/omnichannel/dashboard", {
        headers: { Authorization: `Bearer ${bearer.trim()}` },
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(response.status === 401 ? "Authentification refusée." :
          response.status === 403 ? "Accès tenant ou rôle refusé." :
          "Cockpit indisponible (HTTP " + response.status + ").");
      }
      const data = (await response.json()) as Dashboard;
      if (!data || typeof data.tenant_id !== "string" || !Array.isArray(data.workers) || !data.queues ||
          !data.delivery || !Array.isArray(data.alerts) || !Array.isArray(data.incidents)) {
        throw new Error("Réponse de supervision invalide.");
      }
      setDashboard(data);
    } catch (err) {
      setDashboard(null);
      setError(err instanceof Error ? err.message : "Erreur inconnue.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!autoRefresh || !token) return;
    const interval = setInterval(() => {
      if (document.visibilityState === "visible" && tokenRef.current) {
        void load(tokenRef.current);
      }
    }, 30000);
    return () => clearInterval(interval);
  }, [autoRefresh, token, load]);

  const acknowledge = async (code: string) => {
    if (!token.trim() || busyCode) return;
    setBusyCode(code);
    setError("");
    try {
      const response = await fetch(
        `/api/omnichannel/incidents/${encodeURIComponent(code)}/acknowledge`,
        { method: "POST", headers: { Authorization: `Bearer ${token.trim()}` },
          cache: "no-store" },
      );
      if (!response.ok) {
        throw new Error(response.status === 403 ? "Rôle opérateur requis." :
          response.status === 404 ? "Incident déjà traité ou introuvable." :
          "Acquittement indisponible.");
      }
      await load(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Acquittement impossible.");
    } finally {
      setBusyCode(null);
    }
  };

  const queues = dashboard ? [
    { name: "Entrants", item: dashboard.queues.inbound },
    { name: "Routage", item: dashboard.queues.routes },
    { name: "Sortants", item: dashboard.queues.outbound },
  ] : [];

  return (
    <main className="min-h-screen bg-slate-50 p-5 text-slate-900 md:p-10">
      <div className="mx-auto max-w-7xl space-y-7">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Link href="/dashboard" className="text-sm text-blue-700 hover:underline">
              ← RKJO Dashboard
            </Link>
            <p className="mt-4 text-xs font-bold uppercase tracking-widest text-blue-700">
              RKJO AI Platform · Stream E
            </p>
            <h1 className="mt-1 text-3xl font-bold">Omnichannel · Centre de supervision</h1>
            <p className="mt-2 text-sm text-slate-600">
              Exploitation multitenant · Alertes, files et livraison fournisseur
            </p>
          </div>
          {dashboard && <div className="rounded-xl border bg-white px-5 py-3 text-sm">
            <div className="font-semibold">Tenant : {dashboard.tenant_id}</div>
            <div className="text-slate-500">Actualisé le {formatDate(dashboard.evaluated_at)}</div>
          </div>}
        </header>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-label="Connexion sécurisée">
          <label htmlFor="rkjo-cockpit-token" className="block text-sm font-semibold">
            Jeton Bearer utilisateur (tenant-bound)
          </label>
          <p className="mt-1 text-xs text-slate-500">
            Conservé uniquement dans cette page, jamais dans localStorage, les cookies ou l'URL.
            Utilise un jeton à durée limitée ; ne colle pas de clé API partagée.
          </p>
          <div className="mt-3 flex flex-wrap gap-3">
            <input
              id="rkjo-cockpit-token"
              type="password"
              autoComplete="off"
              value={token}
              onChange={(event) => { setToken(event.target.value); setDashboard(null); }}
              placeholder="Coller un jeton d'accès utilisateur"
              className="min-w-0 flex-1 rounded-xl border border-slate-300 px-4 py-3 text-sm"
            />
            <button
              type="button"
              disabled={loading || !token.trim()}
              onClick={() => void load(token)}
              className="rounded-xl bg-blue-800 px-5 py-3 text-sm font-semibold text-white disabled:opacity-40"
            >
              {loading ? "Chargement…" : "Actualiser"}
            </button>
            <button type="button" onClick={() => { setAutoRefresh(false); setToken(""); setDashboard(null); setError(""); }}
              className="rounded-xl border border-slate-300 px-4 py-3 text-sm">
              Déconnecter
            </button>
          </div>
          <label className="mt-3 flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={autoRefresh}
              onChange={(event) => setAutoRefresh(event.target.checked)} />
            Actualiser toutes les 30 secondes (onglet visible uniquement)
          </label>
        </section>

        {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</div>}

        {!dashboard && !loading &&
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center text-slate-500">
            Identifie-toi avec un jeton autorisé pour charger les données réelles du cockpit.
            Aucun chiffre de démonstration n'est présenté comme donnée de production.
          </div>}

        {dashboard && <>
          <section className="grid gap-4 md:grid-cols-4" aria-label="Indicateurs de synthèse">
            {[
              { title: "Alertes actives", number: dashboard.alerts.length },
              { title: "Envois incertains", number: dashboard.delivery.uncertain_outbound },
              { title: "Preuves non finalisées", number: dashboard.delivery.provider_confirmed_uncommitted },
              { title: "Accusés de réception", number: dashboard.delivery.delivery_receipts },
            ].map((metric) =>
              <article key={metric.title} className="rounded-2xl border bg-white p-5 shadow-sm">
                <p className="text-sm text-slate-500">{metric.title}</p>
                <p className="mt-2 text-3xl font-bold tabular-nums">{metric.number.toLocaleString("fr-FR")}</p>
              </article>)}
          </section>

          <section className="grid gap-4 lg:grid-cols-3" aria-label="Santé des files">
            {queues.map(({ name, item }) =>
              <article key={name} className="rounded-2xl border bg-white p-5 shadow-sm">
                <h2 className="text-lg font-bold">{name}</h2>
                <div className="mt-5 grid grid-cols-3 gap-2 text-center">
                  {[
                    ["En attente", item.pending],
                    ["Échecs", item.failed],
                    ["Leases expirés", item.expired_leases],
                  ].map(([title, count]) =>
                    <div key={String(title)} className="rounded-lg bg-slate-50 p-3">
                      <p className="text-xl font-bold tabular-nums">{count}</p>
                      <p className="mt-1 text-xs text-slate-500">{title}</p>
                    </div>)}
                </div>
              </article>)}
          </section>

          <section className="rounded-2xl border bg-white p-5 shadow-sm" aria-label="Workers supervisés">
            <h2 className="text-xl font-bold">Workers supervisés</h2>
            <p className="mt-1 text-xs text-slate-500">Heartbeats déclarés pour ce tenant. Absence de heartbeat ≠ disponibilité confirmée.</p>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {dashboard.workers.length === 0 && <p className="text-sm text-slate-500">Aucun worker déclaré pour ce tenant.</p>}
              {dashboard.workers.map((worker) => <article key={worker.name} className="flex items-center justify-between rounded-xl border p-4">
                <div><p className="font-semibold">{worker.name}</p>
                  <p className="text-xs text-slate-500">Dernier heartbeat : {formatDate(worker.last_seen_at)}</p></div>
                <span className={worker.stale || worker.status !== "ready" ?
                  "rounded-full bg-amber-100 px-3 py-1 text-xs text-amber-800" :
                  "rounded-full bg-emerald-100 px-3 py-1 text-xs text-emerald-800"}>
                  {worker.stale ? "Périmé" : worker.status === "ready" ? "Disponible" : worker.status}
                </span>
              </article>)}
            </div>
          </section>

          <section className="grid gap-5 lg:grid-cols-5">
            <div className="rounded-2xl border bg-white p-5 shadow-sm lg:col-span-2">
              <h2 className="text-xl font-bold">Alertes détectées</h2>
              <p className="mt-1 text-xs text-slate-500">Évaluation courante du monitoring</p>
              <div className="mt-4 space-y-3">
                {dashboard.alerts.length === 0 && <p className="text-sm text-emerald-700">Aucune alerte détectée.</p>}
                {dashboard.alerts.map((alert) =>
                  <article key={alert.code} className="rounded-xl border border-slate-200 p-4">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold">{label(alert.code)}</span>
                      <span className={alert.severity === "critical" ?
                        "rounded-full bg-red-100 px-2 py-1 text-xs text-red-800" :
                        "rounded-full bg-amber-100 px-2 py-1 text-xs text-amber-800"}>
                        {alert.severity === "critical" ? "Critique" : "Avertissement"}
                      </span>
                    </div>
                    <p className="mt-2 text-sm text-slate-500">Occurrences : {alert.count}</p>
                  </article>)}
              </div>
            </div>

            <div className="rounded-2xl border bg-white p-5 shadow-sm lg:col-span-3">
              <h2 className="text-xl font-bold">Incidents à traiter</h2>
              <p className="mt-1 text-xs text-slate-500">
                Acquittement réservé aux opérateurs. Il n'entraîne aucun renvoi de message.
              </p>
              <div className="mt-4 space-y-3">
                {dashboard.incidents.length === 0 && <p className="text-sm text-slate-500">Aucun incident ouvert enregistré.</p>}
                {dashboard.incidents.map((item) =>
                  <article key={item.code} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4">
                    <div>
                      <p className="text-sm font-semibold">{label(item.code)}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {item.status === "acknowledged" ? "Acquitté" : "Ouvert"} · {item.count} cas · {formatDate(item.last_seen_at)}
                      </p>
                    </div>
                    {item.status === "open" ?
                      <button type="button" disabled={busyCode !== null}
                        onClick={() => void acknowledge(item.code)}
                        className="rounded-lg border border-blue-700 px-3 py-2 text-xs font-semibold text-blue-800 disabled:opacity-50">
                        {busyCode === item.code ? "Traitement…" : "Acquitter"}
                      </button> :
                      <span className="rounded-lg bg-slate-100 px-3 py-2 text-xs text-slate-500">En cours de traitement</span>}
                  </article>)}
              </div>
            </div>
          </section>

          <p className="text-xs text-slate-500">
            Les files et alertes sont réelles, limitées au tenant authentifié. Les métriques RabbitMQ globales (consommateurs, profondeur des queues et DLQ)
            ne sont pas encore exposées : un heartbeat ne mesure pas la santé complète du broker.
          </p>
        </>}
      </div>
    </main>
  );
}
