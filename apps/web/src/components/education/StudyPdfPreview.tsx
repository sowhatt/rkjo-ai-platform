"use client";

import { FormEvent, useState } from "react";

type Outline = { title: string; body: string; pages: number[] };
type Preview = {
  document_id: string;
  ue_id: string;
  document_type: string;
  pages_with_text: number;
  preview_only: boolean;
  revision_outline: Outline[];
};

const suggestedUnits: Record<string, string[]> = {
  "medicine-year-1": [
    "Anatomie", "Physiologie", "Biologie cellulaire", "Histologie",
    "Biochimie", "Biophysique", "Embryologie", "Santé publique",
  ],
  "pharmacy-year-1": [
    "Chimie générale", "Chimie organique", "Biochimie", "Biologie cellulaire",
    "Physiologie", "Botanique", "Pharmacologie", "Microbiologie",
  ],
  "nursing-year-1": [
    "Sciences biologiques et médicales", "Anatomie et physiologie",
    "Hygiène et infectiologie", "Soins infirmiers", "Pharmacologie",
    "Santé publique", "Psychologie", "Raisonnement clinique",
  ],
};

export default function StudyPdfPreview() {
  const [programme, setProgramme] = useState("medicine-year-1");
  const [ue, setUe] = useState("");
  const [kind, setKind] = useState("cm");
  const [token, setToken] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPreview(null);
    if (!file || file.type !== "application/pdf" || file.size > 15 * 1024 * 1024) {
      setError("Choisis un PDF de 15 Mo maximum.");
      return;
    }
    if (!token.trim()) {
      setError("Un jeton étudiant temporaire est nécessaire pour ce pilote.");
      return;
    }
    const form = new FormData();
    form.append("file", file);
    form.append("programme_id", programme.trim());
    form.append("ue_id", ue.trim());
    form.append("document_type", kind);
    setLoading(true);
    try {
      const response = await fetch("/api/education/study/preview-pdf", {
        method: "POST",
        headers: { authorization: `Bearer ${token.trim()}` },
        body: form,
        cache: "no-store",
      });
      const data: unknown = await response.json();
      if (!response.ok) {
        const detail = data && typeof data === "object" && "detail" in data ? String(data.detail) : "Import impossible.";
        throw new Error(detail);
      }
      if (!data || typeof data !== "object" || !("revision_outline" in data) ||
          !Array.isArray(data.revision_outline)) {
        throw new Error("La réponse du serveur est invalide.");
      }
      setPreview(data as Preview);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Erreur pendant la lecture du PDF.");
    } finally {
      setToken("");
      setLoading(false);
    }
  }

  return (
    <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" aria-labelledby="study-pdf-heading">
      <p className="text-xs font-semibold uppercase tracking-widest text-blue-700">Pilote étudiant · Stream D + B</p>
      <h2 id="study-pdf-heading" className="mt-2 text-2xl font-bold">Importer un cours PDF</h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        Prévisualise le texte extrait de ton CM, TD ou TP et retrouve les pages du document.
        Il s&apos;agit d&apos;extraits, pas encore d&apos;une fiche rédigée par IA.
      </p>
      <form onSubmit={onSubmit} className="mt-6 grid gap-4 sm:grid-cols-2">
        <label className="block text-sm font-semibold">
          Formation
          <select value={programme} onChange={(event) => {
            setProgramme(event.target.value);
            setUe("");
          }}
            className="mt-2 w-full rounded-lg border border-slate-300 bg-white p-3">
            <option value="medicine-year-1">Médecine</option>
            <option value="pharmacy-year-1">Pharmacie</option>
            <option value="nursing-year-1">Soins infirmiers</option>
          </select>
        </label>
        <label className="block text-sm font-semibold">
          Unité d&apos;enseignement
          <input required maxLength={120} list="suggested-health-ues"
            value={ue} onChange={(event) => setUe(event.target.value)}
            className="mt-2 w-full rounded-lg border border-slate-300 p-3"
            placeholder="Choisir une UE ou saisir la tienne" />
          <datalist id="suggested-health-ues">
            {suggestedUnits[programme].map((unit) => (
              <option value={unit} key={unit} />
            ))}
          </datalist>
          <span className="mt-1 block text-xs font-normal text-slate-500">
            Suggestions indicatives : saisis le nom exact de ton UE selon ton établissement.
          </span>
        </label>
        <label className="block text-sm font-semibold">
          Support
          <select value={kind} onChange={(event) => setKind(event.target.value)}
            className="mt-2 w-full rounded-lg border border-slate-300 bg-white p-3">
            <option value="cm">Cours magistral</option>
            <option value="td">Travaux dirigés</option>
            <option value="tp">Travaux pratiques</option>
          </select>
        </label>
        <label className="block text-sm font-semibold">
          PDF (15 Mo maximum)
          <input required type="file" accept=".pdf,application/pdf"
            onChange={(event) => setFile(event.currentTarget.files?.[0] ?? null)}
            className="mt-2 w-full rounded-lg border border-slate-300 p-3 text-sm" />
        </label>
        <label className="block text-sm font-semibold sm:col-span-2">
          Jeton Bearer étudiant temporaire (pilote local uniquement)
          <input type="password" autoComplete="off" value={token}
            onChange={(event) => setToken(event.target.value)}
            className="mt-2 w-full rounded-lg border border-slate-300 p-3"
            placeholder="Jeton de test signé, avec tenant et sujet" />
        </label>
        <p className="text-xs text-slate-500 sm:col-span-2">
          N&apos;utilise pas de documents contenant des données patient. Le jeton n&apos;est ni enregistré
          dans le navigateur ni conservé après la requête. L&apos;API ne stocke pas le PDF.
        </p>
        <button disabled={loading} type="submit"
          className="rounded-xl bg-slate-900 px-6 py-3 font-semibold text-white disabled:opacity-50 sm:col-span-2">
          {loading ? "Analyse du cours…" : "Analyser mon PDF"}
        </button>
      </form>
      {error && <p role="alert" className="mt-5 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
      {preview && (
        <div className="mt-8" aria-live="polite">
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <h3 className="font-bold text-emerald-900">Document analysé</h3>
            <p className="text-sm text-emerald-900">{preview.pages_with_text} page(s) contenant du texte · UE : {preview.ue_id}</p>
            <p className="mt-1 text-xs text-emerald-900">Prévisualisation temporaire · aucune sauvegarde · non validée scientifiquement</p>
          </div>
          <h3 className="mt-6 text-xl font-bold">Extraits avec références au cours</h3>
          <div className="mt-3 grid gap-4">
            {preview.revision_outline.map((item, index) => (
              <article key={index} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <h4 className="font-semibold">{item.title}</h4>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{item.body}</p>
                <p className="mt-3 text-xs font-semibold text-blue-800">Source : page(s) {item.pages.join(", ")}</p>
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
