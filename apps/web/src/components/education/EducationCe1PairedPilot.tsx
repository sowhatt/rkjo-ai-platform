"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

type Role = "teacher" | "learner";
type SessionStatus = "active" | "paused" | "ended";
type State = { session_id: string; status: SessionStatus; version: number };

async function pilotRequest(path: string, token: string, body?: object): Promise<State> {
  const response = await fetch("/api/ce1-pilot/" + path, {
    method: body === undefined ? "GET" : "POST",
    headers: { Authorization: "Bearer " + token, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  const payload: unknown = await response.json();
  if (!response.ok) {
    const detail = typeof payload === "object" && payload !== null && "detail" in payload
      ? String(payload.detail) : "Requête refusée";
    throw new Error(`HTTP ${response.status} : ${detail}`);
  }
  if (typeof payload !== "object" || payload === null || !("version" in payload) || !("status" in payload) || !("session_id" in payload)) {
    throw new Error("Réponse API invalide");
  }
  return payload as State;
}

export default function EducationCe1PairedPilot({ role }: { role: Role }) {
  const [token, setToken] = useState("");
  const [learnerId, setLearnerId] = useState("");
  const [sessionInput, setSessionInput] = useState("");
  const [state, setState] = useState<State | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [polling, setPolling] = useState(false);
  const tokenRef = useRef(token);
  tokenRef.current = token;

  const refresh = useCallback(async () => {
    const session = sessionInput.trim();
    const bearer = tokenRef.current.trim();
    if (!/^[0-9a-fA-F-]{36}$/.test(session) || !bearer) return;
    try {
      const next = await pilotRequest(`${session}/${role === "teacher" ? "teacher-state" : "state"}`, bearer);
      setState(next);
      setError("");
    } catch (err) {
      setState(null); // Fail closed: never treat an unavailable session as active.
      setError(err instanceof Error ? err.message : "Impossible de synchroniser la séance.");
    }
  }, [role, sessionInput]);

  useEffect(() => {
    if (!polling) return;
    let stopped = false;
    async function poll() {
      if (!stopped) await refresh();
    }
    void poll();
    const timer = setInterval(() => void poll(), 2000);
    return () => { stopped = true; clearInterval(timer); };
  }, [polling, refresh]);

  async function create() {
    if (!token.trim() || !/^[0-9a-fA-F-]{36}$/.test(learnerId.trim())) return;
    setBusy(true);
    try {
      const next = await pilotRequest("sessions", token.trim(), { learner_id: learnerId.trim() });
      setSessionInput(next.session_id);
      setState(next);
      setPolling(true);
      setError("");
    } catch (err) {
      setState(null);
      setError(err instanceof Error ? err.message : "Création impossible");
    } finally { setBusy(false); }
  }

  async function command(value: "pause" | "resume" | "end") {
    if (!state || !token.trim()) return;
    setBusy(true);
    try {
      const next = await pilotRequest(`${state.session_id}/commands`, token.trim(), {
        command: value, expected_version: state.version,
      });
      setState(next);
      setError("");
    } catch (err) {
      setState(null);
      setError(err instanceof Error ? err.message : "Commande refusée");
    } finally { setBusy(false); }
  }

  async function submitTurn() {
    if (!state || !token.trim()) return;
    setBusy(true);
    try {
      const next = await pilotRequest(`${state.session_id}/turns`, token.trim(), {
        expected_version: state.version,
      });
      setState(next);
      setError("Activité reçue par le serveur. Ceci n'est pas une correction pédagogique.");
    } catch (err) {
      setState(null);
      setError(err instanceof Error ? err.message : "Activité refusée");
    } finally { setBusy(false); }
  }

  return (
    <main className="min-h-screen bg-slate-50 p-5 text-slate-900">
      <div className="mx-auto max-w-2xl space-y-5">
        <Link href="/education/classe-ce1" className="text-sm font-semibold text-blue-700 underline">← Classe CE1</Link>
        <header className="rounded-2xl bg-slate-900 p-6 text-white">
          <p className="text-sm text-cyan-300">RKJO Education · Recette locale — {role === "teacher" ? "Professeur" : "Élève"}</p>
          <h1 className="mt-2 text-2xl font-bold">Séance CE1 connectée — contrôle de pause</h1>
          <p className="mt-2 text-sm text-amber-200">Pilote de développement uniquement. Aucun vrai élève ni aucune vraie donnée de mineur. Jeton gardé en mémoire de cette page.</p>
        </header>
        <section className="space-y-3 rounded-2xl border bg-white p-5">
          <label className="block text-sm font-semibold" htmlFor="pilot-token">JWT individuel de test ({role})</label>
          <input id="pilot-token" type="password" autoComplete="off" value={token}
            onChange={(e) => { setToken(e.target.value); setState(null); setPolling(false); }}
            placeholder="Jeton de test local" className="w-full rounded-lg border p-3" />
          {role === "teacher" && (
            <>
              <label className="block text-sm font-semibold" htmlFor="learner-id">Identifiant UUID de l'élève fictif</label>
              <input id="learner-id" value={learnerId} onChange={(e) => setLearnerId(e.target.value)}
                className="w-full rounded-lg border p-3" />
              <button type="button" disabled={busy || !token.trim() || !learnerId.trim()} onClick={create}
                className="rounded-lg bg-blue-700 px-4 py-2 font-semibold text-white disabled:opacity-40">Créer une séance</button>
            </>
          )}
          <label className="block text-sm font-semibold" htmlFor="pilot-session">Identifiant UUID de la séance</label>
          <input id="pilot-session" value={sessionInput}
            onChange={(e) => { setSessionInput(e.target.value); setState(null); setPolling(false); }}
            className="w-full rounded-lg border p-3" />
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => { setPolling(true); void refresh(); }} disabled={!token.trim() || !sessionInput.trim()}
              className="rounded-lg bg-slate-900 px-4 py-2 text-white disabled:opacity-40">Connecter et synchroniser</button>
            <button type="button" onClick={() => setPolling(false)} disabled={!polling}
              className="rounded-lg border px-4 py-2 disabled:opacity-40">Arrêter le suivi</button>
          </div>
        </section>
        <section className="space-y-3 rounded-2xl border bg-white p-5">
          <h2 className="text-xl font-semibold">État de séance provenant du serveur</h2>
          <p role="status" className="text-lg font-semibold">{state === null ? "État inconnu — actions désactivées" : state.status === "active" ? "Active" : state.status === "paused" ? "En pause" : "Terminée"}</p>
          <p className="text-sm text-slate-600">Version serveur : {state?.version ?? "—"} · Synchronisation {polling ? "toutes les 2 secondes" : "arrêtée"}</p>
          {role === "teacher" ? (
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => void command("pause")} disabled={busy || !state || state.status !== "active"}
                className="rounded-lg bg-amber-600 px-4 py-2 font-semibold text-white disabled:opacity-40">Pause</button>
              <button type="button" onClick={() => void command("resume")} disabled={busy || !state || state.status !== "paused"}
                className="rounded-lg bg-blue-700 px-4 py-2 font-semibold text-white disabled:opacity-40">Reprendre</button>
              <button type="button" onClick={() => void command("end")} disabled={busy || !state || state.status === "ended"}
                className="rounded-lg border px-4 py-2 font-semibold disabled:opacity-40">Terminer</button>
            </div>
          ) : (
            <button type="button" onClick={() => void submitTurn()} disabled={busy || !state || state.status !== "active"}
              className="rounded-lg bg-blue-700 px-4 py-3 font-semibold text-white disabled:opacity-40">Envoyer une activité test</button>
          )}
          {error && <p role="alert" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-950">{error}</p>}
        </section>
      </div>
    </main>
  );
}
