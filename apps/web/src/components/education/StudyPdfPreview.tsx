"use client";

import { FormEvent, useEffect, useState } from "react";

type Outline = { title: string; body: string; pages: number[] };
type Citation = { page: number; segment_id: string };
type RevisionNote = { title: string; excerpts: string[]; citation: Citation; source_only: boolean };
type MindMapBranch = { id: string; label: string; page: number; children: { label: string; text: string; citation: Citation }[] };
type GeneratedItem = { title: string; body: string; pages: number[] };
type Preview = {
  ai_materials: { revision_note: GeneratedItem[]; mind_map: GeneratedItem[]; mode: string } | null;
  revision_notes: RevisionNote[];
  mind_map: { root: string; branches: MindMapBranch[]; representation: string };
  generation_mode: string;
  disclaimer: string;
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
  const [connected, setConnected] = useState(false);
  const [password, setPassword] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [generateAi, setGenerateAi] = useState(false);
  const [studyTab, setStudyTab] = useState<"notes" | "map" | "sources">("notes");

  useEffect(() => {
    let mounted = true;
    fetch("/api/education/study/session", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return;
        const data: { connected?: boolean } = await response.json();
        if (mounted) setConnected(Boolean(data.connected));
      })
      .catch(() => undefined);
    return () => { mounted = false; };
  }, []);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAuthBusy(true);
    setError("");
    try {
      const response = await fetch("/api/education/study/session", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ password }),
        cache: "no-store",
      });
      if (!response.ok) throw new Error("Connexion impossible : vérifie le code pilote local.");
      setConnected(true);
      setPassword("");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Connexion impossible.");
    } finally { setAuthBusy(false); }
  }

  async function logout() {
    await fetch("/api/education/study/session", { method: "DELETE", cache: "no-store" });
    setConnected(false);
    setPreview(null);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPreview(null);
    if (!file || file.type !== "application/pdf" || file.size > 15 * 1024 * 1024) {
      setError("Choisis un PDF de 15 Mo maximum.");
      return;
    }
    if (!connected) {
      setError("Connecte-toi au pilote avant d’analyser un cours.");
      return;
    }
    const form = new FormData();
    form.append("file", file);
    form.append("programme_id", programme.trim());
    form.append("ue_id", ue.trim());
    form.append("document_type", kind);
    form.append("generate_ai", String(generateAi));
    setLoading(true);
    try {
      const response = await fetch("/api/education/study/preview-pdf", {
        method: "POST",
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
      const result = data as Preview;
      if (!Array.isArray(result.revision_notes) || !Array.isArray(result.mind_map?.branches)) {
        throw new Error("Vues pédagogiques absentes de la réponse API.");
      }
      setStudyTab("notes");
      setPreview(result);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Erreur pendant la lecture du PDF.");
    } finally {
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
      <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
        {connected ? (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm font-semibold text-emerald-800">Connecté au pilote étudiant local</p>
            <button type="button" onClick={logout} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold">
              Se déconnecter
            </button>
          </div>
        ) : (
          <form onSubmit={login} className="flex flex-wrap items-end gap-3">
            <label className="min-w-48 flex-1 text-sm font-semibold">
              Code de connexion du pilote
              <input required type="password" autoComplete="off" maxLength={256}
                value={password} onChange={(event) => setPassword(event.target.value)}
                className="mt-2 w-full rounded-lg border border-slate-300 bg-white p-3"
                placeholder="Code fourni par le responsable du pilote" />
            </label>
            <button disabled={authBusy} type="submit"
              className="rounded-lg bg-blue-700 px-5 py-3 text-sm font-semibold text-white disabled:opacity-50">
              {authBusy ? "Connexion…" : "Se connecter"}
            </button>
          </form>
        )}
        <p className="mt-2 text-xs text-slate-500">Accès de démonstration local uniquement, sans compte étudiant permanent.</p>
      </div>
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
        <p className="text-xs text-slate-500 sm:col-span-2">
          N&apos;utilise pas de documents contenant des données patient. La session est gérée par
          un cookie HttpOnly ; l&apos;API ne stocke pas le PDF.
        </p>
        <label className="sm:col-span-2 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
          <input type="checkbox" checked={generateAi} onChange={(event) => setGenerateAi(event.target.checked)}
            className="mt-1" />
          <span><strong>Essayer les fiches et cartes générées par IA (optionnel)</strong><br />
            Si le pilote IA est activé, des extraits de mon document seront envoyés au fournisseur IA configuré.
            Le résultat est expérimental, doit être vérifié avec le cours et ne constitue pas un avis médical.
            Si je laisse cette case décochée, seul le traitement local par extraits est utilisé.
          </span>
        </label>
        <button disabled={loading || !connected} type="submit"
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
          <div className="mt-6 flex flex-wrap gap-2" role="tablist" aria-label="Supports de révision">
            {([
              ["notes", "Fiches de révision"],
              ["map", "Carte des notions"],
              ["sources", "Extraits du PDF"],
            ] as const).map(([id, title]) => (
              <button key={id} type="button" role="tab" aria-selected={studyTab === id}
                onClick={() => setStudyTab(id)}
                className={`rounded-lg px-4 py-2 text-sm font-semibold ${studyTab === id ? "bg-blue-700 text-white" : "border border-slate-300 bg-white text-slate-800"}`}>
                {title}
              </button>
            ))}
          </div>
          <p className="mt-3 text-sm text-amber-900">{preview.disclaimer}</p>
          {preview.ai_materials && (
            <div className="mt-4 rounded-lg border border-violet-200 bg-violet-50 p-4">
              <p className="font-semibold">Supports générés par IA · à vérifier avec les pages du cours</p>
              <p className="mt-1 text-xs">Ces contenus sont des propositions pédagogiques non validées.</p>
              <div className="mt-3 grid gap-3">
                {(studyTab === "map" ? preview.ai_materials.mind_map :
                  studyTab === "notes" ? preview.ai_materials.revision_note : []).map((item, index) => (
                  <article key={index} className="rounded-lg border border-violet-100 bg-white p-3">
                    <h4 className="font-semibold">{item.title}</h4>
                    <p className="mt-2 whitespace-pre-wrap text-sm">{item.body}</p>
                    <p className="mt-2 text-xs text-blue-800">Références déclarées : page(s) {item.pages.join(", ")}</p>
                  </article>
                ))}
              </div>
            </div>
          )}
          {studyTab === "notes" && (
            <section aria-label="Fiches de révision" className="mt-4 grid gap-3">
              {preview.revision_notes.map((note) => (
                <article key={note.citation.segment_id} className="rounded-xl border border-slate-200 bg-white p-4">
                  <h3 className="font-semibold">{note.title}</h3>
                  <ul className="mt-2 list-disc space-y-2 pl-5 text-sm">
                    {note.excerpts.map((excerpt, i) => <li key={i}>{excerpt}</li>)}
                  </ul>
                  <p className="mt-2 text-xs text-blue-800">Extraits du cours · page {note.citation.page}</p>
                </article>
              ))}
            </section>
          )}
          {studyTab === "map" && (
            <section aria-label="Carte des notions" className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
              <h3 className="text-lg font-bold">{preview.mind_map.root}</h3>
              <p className="mt-1 text-xs text-slate-600">Plan navigable extrait des pages ; relations conceptuelles IA à venir.</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {preview.mind_map.branches.map((branch) => (
                  <details key={branch.id} className="rounded-lg border border-blue-200 bg-blue-50 p-3">
                    <summary className="cursor-pointer font-semibold">{branch.label} · p. {branch.page}</summary>
                    <ul className="mt-2 list-disc space-y-2 pl-4 text-sm">
                      {branch.children.map((child, i) => <li key={i}>{child.text}</li>)}
                    </ul>
                  </details>
                ))}
              </div>
            </section>
          )}
          {studyTab === "sources" && (
          <>
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
          </>
          )}
        </div>
      )}
    </section>
  );
}
