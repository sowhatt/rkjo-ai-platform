"use client";

import { FormEvent, useState } from "react";
import { useSearchParams } from "next/navigation";
import EducationShell from "@/components/education/EducationShell";

type QuestionAlignment = {
  question_ref: string;
  competency_code: string | null;
  alignment_confidence: number;
  requires_confirmation: boolean;
  earned_points: number | null;
  max_points: number | null;
};

type Analysis = {
  document_id: string;
  source_hash: string;
  kind: string;
  provenance: string;
  questions: QuestionAlignment[];
};

const demoReferential = [
  { code: "MED.BIO.CELL", label: "Biologie cellulaire", keywords: ["cellule", "membrane", "mitochondrie"], importance: 3 },
  { code: "MED.BIO.GEN", label: "Génétique", keywords: ["adn", "gène", "chromosome"], importance: 3 },
];

export default function EducationResources() {
  const params = useSearchParams();
  const learnerId = params.get("learnerId") ?? "";
  const [kind, setKind] = useState("corrected_copy");
  const [filename, setFilename] = useState("copie-corrigee.pdf");
  const [text, setText] = useState("");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [corrections, setCorrections] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function analyze(event: FormEvent) {
    event.preventDefault();
    if (!learnerId || !text.trim()) return;
    setLoading(true); setError("");
    try {
      const response = await fetch("/api/education/documents/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          learner_id: learnerId,
          filename,
          media_type: "application/pdf",
          extracted_text: text,
          kind,
          provenance: "learner_upload",
          referential: demoReferential,
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "Analyse impossible.");
      setAnalysis(payload as Analysis);
      setCorrections({});
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Analyse impossible.");
    } finally { setLoading(false); }
  }

  return (
    <EducationShell active="resources">
      <header className="rkjo-demo-header">
        <div>
          <span className="rkjo-edu-kicker">MES SUPPORTS</span>
          <h1>Montre à RKJO ce que tu étudies</h1>
          <p>Ajoute un cours, un TD ou une copie corrigée. RKJO te montre ce qu&apos;il a compris avant d&apos;utiliser ces informations pour ton apprentissage.</p>
        </div>
      </header>

      <section className="rkjo-session-main">
        <form onSubmit={analyze}>
          <label>Type de support
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="course">Cours</option>
              <option value="td">TD / exercices</option>
              <option value="corrected_copy">Copie corrigée</option>
              <option value="exam">Ancien examen</option>
            </select>
          </label>
          <label>Nom du fichier
            <input value={filename} onChange={(e) => setFilename(e.target.value)} />
          </label>
          <label>Contenu extrait
            <textarea rows={8} value={text} onChange={(e) => setText(e.target.value)} placeholder={"Question 1: cellule et membrane. 2/2\nQuestion 2: expliquer l'ADN. 1/3"} />
          </label>
          <button className="rkjo-start" disabled={loading || !learnerId || !text.trim()}>
            {loading ? "RKJO analyse…" : "Analyser mon support"}
          </button>
          {!learnerId ? <p>Ouvre cette page depuis ton espace étudiant pour associer le support à ton profil.</p> : null}
        </form>
      </section>

      {error ? <div className="rkjo-session-error">{error}</div> : null}

      {analysis ? (
        <section className="rkjo-session-main" aria-live="polite">
          <span className="rkjo-edu-kicker">CE QUE RKJO A COMPRIS</span>
          <p>Source : {analysis.provenance === "learner_upload" ? "ton document" : analysis.provenance}</p>
          {analysis.questions.length === 0 ? (
            <p>Support enregistré. L&apos;alignement détaillé sera proposé quand des questions sont détectées.</p>
          ) : analysis.questions.map((item) => (
            <article key={item.question_ref} className="rkjo-tutor-intro">
              <div>
                <strong>{item.question_ref.toUpperCase()}</strong>
                <p>
                  {item.competency_code ?? "Compétence non reconnue"} · confiance {Math.round(item.alignment_confidence * 100)}%
                  {item.earned_points !== null && item.max_points !== null ? ` · note ${item.earned_points}/${item.max_points}` : ""}
                </p>
                {item.requires_confirmation ? (
                  <label>
                    RKJO n&apos;est pas assez sûr. Confirme ou corrige la compétence :
                    <select
                      value={corrections[item.question_ref] ?? item.competency_code ?? ""}
                      onChange={(e) => setCorrections((current) => ({ ...current, [item.question_ref]: e.target.value }))}
                    >
                      <option value="">Choisir une compétence</option>
                      {demoReferential.map((competency) => <option key={competency.code} value={competency.code}>{competency.label}</option>)}
                    </select>
                  </label>
                ) : <small>✓ Alignement suffisamment fiable</small>}
              </div>
            </article>
          ))}
        </section>
      ) : null}
    </EducationShell>
  );
}
