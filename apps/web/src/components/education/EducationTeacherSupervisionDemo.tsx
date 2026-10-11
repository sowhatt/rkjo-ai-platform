"use client";

import Link from "next/link";
import { useState } from "react";

type SessionStatus = "active" | "paused" | "ended";
type Alert = { id: string; message: string; acknowledged: boolean };

export default function EducationTeacherSupervisionDemo() {
  const [status, setStatus] = useState<SessionStatus>("active");
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [history, setHistory] = useState<string[]>(["Séance CE1 de démonstration ouverte."]);

  function command(next: SessionStatus) {
    if (status === "ended") return;
    if (status === next) return;
    setStatus(next);
    setHistory((old) => [...old, next === "paused" ? "Séance mise en pause." :
      next === "active" ? "Séance reprise." : "Séance terminée."]);
  }

  function simulateAlert() {
    const id = String(Date.now()) + "-" + alerts.length;
    setAlerts((old) => [...old, {
      id,
      message: "Élève fictif : demande de soutien pédagogique à examiner.",
      acknowledged: false,
    }]);
    setHistory((old) => [...old, "Alerte de démonstration reçue."]);
  }

  function acknowledge(id: string) {
    setAlerts((old) => old.map((alert) => alert.id === id ? { ...alert, acknowledged: true } : alert));
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900">
      <div className="mx-auto max-w-4xl space-y-5">
        <Link href="/education/classe-ce1" className="text-sm font-semibold text-blue-700 underline">← Retour à la classe CE1</Link>
        <header className="rounded-2xl bg-slate-900 p-6 text-white">
          <p className="text-xs uppercase tracking-widest text-cyan-300">RKJO Education · Stream B/T</p>
          <h1 className="mt-2 text-3xl font-bold">Supervision du professeur</h1>
          <p className="mt-3 text-sm text-amber-200">Prototype local : aucune identité réelle, aucun élève suivi, aucune commande transmise au serveur.</p>
        </header>
        <section className="rounded-2xl border bg-white p-5" aria-labelledby="teacher-controls">
          <h2 id="teacher-controls" className="text-xl font-bold">Commandes de séance — simulation</h2>
          <p className="mt-2">État : <strong role="status">{status === "active" ? "Active" : status === "paused" ? "En pause" : "Terminée"}</strong></p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button type="button" onClick={() => command("paused")} disabled={status !== "active"} className="rounded-lg bg-amber-600 px-4 py-3 font-semibold text-white disabled:opacity-40">Mettre en pause</button>
            <button type="button" onClick={() => command("active")} disabled={status !== "paused"} className="rounded-lg bg-blue-700 px-4 py-3 font-semibold text-white disabled:opacity-40">Reprendre</button>
            <button type="button" onClick={() => command("ended")} disabled={status === "ended"} className="rounded-lg border border-slate-400 px-4 py-3 font-semibold disabled:opacity-40">Terminer</button>
          </div>
        </section>
        <section className="rounded-2xl border bg-white p-5" aria-labelledby="teacher-alerts">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="teacher-alerts" className="text-xl font-bold">Alertes de sécurité — simulation</h2>
            <button type="button" onClick={simulateAlert} className="rounded-lg border border-blue-700 px-4 py-2 font-semibold text-blue-700">Simuler une alerte</button>
          </div>
          <p className="mt-2 text-sm text-slate-600">Ces messages sont fictifs. Ils illustrent la liaison S → T prévue dans ton schéma.</p>
          <div className="mt-4 space-y-3" aria-live="polite">
            {alerts.length === 0 && <p className="text-sm text-slate-500">Aucune alerte simulée.</p>}
            {alerts.map((alert) => (
              <article key={alert.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-amber-50 p-4">
                <div>
                  <p className="font-medium">{alert.message}</p>
                  <p className="text-sm">{alert.acknowledged ? "Accusé de réception enregistré localement" : "En attente de prise en charge"}</p>
                </div>
                <button type="button" onClick={() => acknowledge(alert.id)} disabled={alert.acknowledged} className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-40">Accuser réception</button>
              </article>
            ))}
          </div>
        </section>
        <section className="rounded-2xl border bg-white p-5">
          <h2 className="text-xl font-bold">Journal de démonstration</h2>
          <ol className="mt-3 list-inside list-decimal space-y-1 text-sm">{history.map((entry, i) => <li key={i}>{entry}</li>)}</ol>
        </section>
      </div>
    </main>
  );
}
