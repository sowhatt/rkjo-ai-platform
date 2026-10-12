"use client";

import { FormEvent, useState } from "react";

type InspectedAudio = {
  filename: string;
  source_id?: string;
  state?: string;
  expires_at?: string;
  duration_ms: number;
  size_bytes: number;
  sample_rate: number;
  channels: number;
  sha256: string;
  inspection_only: boolean;
  stored: boolean;
  transcription_started: boolean;
};

export default function StudyAudioInspect() {
  const [programme, setProgramme] = useState("medicine-year-1");
  const [ue, setUe] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [recordingAuthorized, setRecordingAuthorized] = useState(false);
  const [rightsConfirmed, setRightsConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [stageMode, setStageMode] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<InspectedAudio | null>(null);

  async function inspect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setResult(null);
    setError("");
    if (!file || file.size > 50 * 1024 * 1024 || file.size === 0 ||
        !["audio/wav", "audio/x-wav", "audio/wave"].includes(file.type)) {
      setError("Choisis un WAV non vide de 50 Mo maximum.");
      return;
    }
    if (!recordingAuthorized || !rightsConfirmed) {
      setError("Les deux autorisations sont obligatoires.");
      return;
    }
    const payload = new FormData();
    payload.append("file", file);
    payload.append("programme_id", programme);
    payload.append("ue_id", ue.trim());
    payload.append("recording_authorized", "true");
    payload.append("processing_rights_confirmed", "true");
    setLoading(true);
    try {
      const response = await fetch(stageMode ? "/api/education/study/stage-audio" : "/api/education/study/inspect-audio", {
        method: "POST", body: payload, cache: "no-store",
      });
      const data: unknown = await response.json();
      if (!response.ok) {
        const message = data && typeof data === "object" && "detail" in data
          ? String(data.detail) : "Import non validé.";
        throw new Error(message);
      }
      setResult(data as InspectedAudio);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Inspection impossible.");
    } finally { setLoading(false); }
  }

  return (
    <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-widest text-blue-700">Stream D + E + F/S · Premier import réel</p>
      <h2 className="mt-2 text-xl font-bold">Vérifier un cours magistral audio</h2>
      <p className="mt-2 text-sm text-slate-600">
        Inspection WAV disponible ; stockage PostgreSQL temporaire possible uniquement en pilote local activé.
        Aucune transcription, résumé ou paiement ne démarre.
      </p>
      <form onSubmit={inspect} className="mt-5 grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-semibold">
          Formation
          <select value={programme} onChange={event => setProgramme(event.target.value)}
            className="mt-2 w-full rounded-lg border border-slate-300 bg-white p-3">
            <option value="medicine-year-1">Médecine</option>
            <option value="pharmacy-year-1">Pharmacie</option>
            <option value="nursing-year-1">Soins infirmiers</option>
          </select>
        </label>
        <label className="text-sm font-semibold">
          Unité d&apos;enseignement
          <input required maxLength={120} value={ue} onChange={event => setUe(event.target.value)}
            placeholder="Ex. Physiologie" className="mt-2 w-full rounded-lg border border-slate-300 p-3"/>
        </label>
        <label className="text-sm font-semibold sm:col-span-2">
          Fichier audio WAV (50 Mo maximum)
          <input required type="file" accept=".wav,audio/wav,audio/x-wav,audio/wave"
            onChange={event => { setFile(event.target.files?.[0] ?? null); setResult(null); }}
            className="mt-2 w-full rounded-lg border border-slate-300 p-3"/>
        </label>
        <label className="flex items-start gap-2 text-sm sm:col-span-2">
          <input required type="checkbox" checked={recordingAuthorized}
            onChange={event=>setRecordingAuthorized(event.target.checked)} />
          Je confirme que l&apos;enregistrement est autorisé et respecte les personnes enregistrées.
        </label>
        <label className="flex items-start gap-2 text-sm sm:col-span-2">
          <input required type="checkbox" checked={rightsConfirmed}
            onChange={event=>setRightsConfirmed(event.target.checked)} />
          Je suis autorisé à transmettre cet audio pour analyse et il ne contient pas de données patient.
        </label>
        <label className="flex items-start gap-2 text-sm sm:col-span-2">
          <input type="checkbox" checked={stageMode} onChange={event => { setStageMode(event.target.checked); setResult(null); }} />
          Conserver temporairement cet audio dans la base PostgreSQL du pilote (24 h, sans chiffrement applicatif).
        </label>
        <button type="submit" disabled={loading}
          className="rounded-xl bg-slate-900 px-6 py-3 font-semibold text-white disabled:opacity-50 sm:col-span-2">
          {loading ? "Vérification en cours…" : stageMode ? "Enregistrer mon audio (pilote local)" : "Vérifier mon audio"}
        </button>
      </form>
      {error && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-4 text-sm text-red-800">{error}</p>}
      {result && (
        <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4" role="status">
          <p className="font-bold text-emerald-900">{result.source_id ? "Audio enregistré dans le pilote" : "Fichier WAV validé — inspection uniquement"}</p>
          <p className="mt-2 text-sm text-emerald-900">
            Durée : {(result.duration_ms / 60000).toFixed(2)} min ·
            Taille : {(result.size_bytes / 1024 / 1024).toFixed(2)} Mo ·
            {result.sample_rate} Hz · {result.channels} canal/canaux
          </p>
          <p className="mt-2 break-all text-xs text-emerald-900">Empreinte SHA-256 : {result.sha256}</p>
          {result.source_id && <p className="mt-2 text-xs text-emerald-900">Référence : {result.source_id} · expiration : {result.expires_at}</p>}
          <p className="mt-2 text-sm font-medium text-emerald-900">
            {result.source_id ? "Audio sauvegardé temporairement ; aucune transcription ni paiement lancé." : "Aucun fichier sauvegardé ; aucun résumé, paiement ou job de transcription lancé."}
          </p>
        </div>
      )}
    </section>
  );
}
