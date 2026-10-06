"use client";

import { FormEvent, useRef, useState } from "react";
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
type Analysis = { document_id: string; questions: QuestionAlignment[] };

const referential = [
  { code: "MED.BIO.CELL", label: "Biologie cellulaire", keywords: ["cellule", "membrane", "mitochondrie"], importance: 3 },
  { code: "MED.BIO.GEN", label: "Génétique", keywords: ["adn", "gène", "chromosome"], importance: 3 },
];
const labels = Object.fromEntries(referential.map((item) => [item.code, item.label]));

export default function EducationResources() {
  const params = useSearchParams();
  const learnerId = params.get("learnerId") ?? "";
  const inputRef = useRef<HTMLInputElement>(null);
  const [kind, setKind] = useState("corrected_copy");
  const [filename, setFilename] = useState("");
  const [text, setText] = useState("");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [corrections, setCorrections] = useState<Record<string, string>>({});
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function chooseFile(file?: File) {
    if (!file) return;
    setFilename(file.name);
    if (file.type.startsWith("text/")) {
      void file.text().then(setText);
    }
  }

  async function analyze(event: FormEvent) {
    event.preventDefault();
    if (!learnerId || !text.trim()) return;
    setLoading(true); setError("");
    try {
      const response = await fetch("/api/education/documents/analyze", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          learner_id: learnerId, filename: filename || "support.pdf",
          media_type: "application/pdf", extracted_text: text, kind,
          provenance: "learner_upload", referential,
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "Analyse impossible.");
      setAnalysis(payload as Analysis); setCorrections({}); setConfirmed({});
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Analyse impossible.");
    } finally { setLoading(false); }
  }

  return (
    <EducationShell active="resources">
      <header className="rkjo-supports-header">
        <div>
          <span className="rkjo-edu-kicker">MES SUPPORTS</span>
          <h1>Tout ce que tu étudies, au même endroit.</h1>
          <p>RKJO relie tes cours, TD et copies corrigées aux compétences que tu dois réellement maîtriser.</p>
        </div>
        <div className="rkjo-supports-privacy">Privé · associé uniquement à ton espace</div>
      </header>

      <section className="rkjo-supports-workspace">
        <div className="rkjo-supports-step"><span>1</span><div><strong>Ajoute un support</strong><small>PDF, photo ou document de cours</small></div></div>
        <form onSubmit={analyze} className="rkjo-supports-form">
          <div className="rkjo-support-type-grid">
            {[
              ["course","Cours","Notions et chapitres"],
              ["td","TD / Exercices","Travail donné en cours"],
              ["corrected_copy","Copie corrigée","Résultats et erreurs"],
              ["exam","Ancien examen","Format et niveau attendu"],
            ].map(([value,title,description]) => (
              <button type="button" key={value} className={kind === value ? "active" : ""} onClick={() => setKind(value)}>
                <strong>{title}</strong><small>{description}</small>
              </button>
            ))}
          </div>

          <input ref={inputRef} className="rkjo-file-input" type="file" accept=".pdf,.png,.jpg,.jpeg,.txt,.doc,.docx" onChange={(e) => chooseFile(e.target.files?.[0])} />
          <button type="button" className="rkjo-upload-zone" onClick={() => inputRef.current?.click()}>
            <span className="rkjo-upload-icon">↑</span>
            <strong>{filename || "Choisir un fichier"}</strong>
            <small>{filename ? "Document prêt à être analysé" : "PDF, photo, Word · jusqu’à 20 Mo"}</small>
          </button>

          <details className="rkjo-prototype-input">
            <summary>Mode prototype · saisir le contenu du document</summary>
            <textarea rows={6} value={text} onChange={(e) => setText(e.target.value)} placeholder={"Question 1: cellule et membrane. 2/2\nQuestion 2: membrane. 0/2"} />
          </details>

          <div className="rkjo-supports-action">
            <div><strong>RKJO respecte la source</strong><small>Le document original reste distingué du contenu généré par l’IA.</small></div>
            <button className="rkjo-action-primary" disabled={loading || !learnerId || !text.trim()}>
              {loading ? "Analyse en cours…" : "Analyser avec RKJO"}
            </button>
          </div>
          {!learnerId ? <p className="rkjo-support-warning">Ce support doit être ouvert depuis un profil étudiant.</p> : null}
        </form>
      </section>

      {error ? <div className="rkjo-session-error">{error}</div> : null}

      {analysis ? (
        <section className="rkjo-analysis-panel" aria-live="polite">
          <div className="rkjo-supports-step"><span>2</span><div><strong>Vérifie ce que RKJO a compris</strong><small>Rien d’incertain n’est utilisé sans ta validation.</small></div></div>
          <div className="rkjo-analysis-summary">
            <strong>{analysis.questions.length} question{analysis.questions.length > 1 ? "s" : ""} détectée{analysis.questions.length > 1 ? "s" : ""}</strong>
            <span>{analysis.questions.filter((q) => !q.requires_confirmation).length} alignement(s) fiable(s)</span>
          </div>
          <div className="rkjo-alignment-list">
            {analysis.questions.map((item) => {
              const selected = corrections[item.question_ref] ?? item.competency_code ?? "";
              const isConfirmed = confirmed[item.question_ref] || !item.requires_confirmation;
              return (
                <article key={item.question_ref} className={isConfirmed ? "confirmed" : "needs-review"}>
                  <div className="rkjo-alignment-number">{item.question_ref.replace(/question[_ ]?/i, "Q")}</div>
                  <div className="rkjo-alignment-content">
                    <div className="rkjo-alignment-title">
                      <strong>{selected ? labels[selected] ?? selected : "Compétence à identifier"}</strong>
                      <span>{Math.round(item.alignment_confidence * 100)}% de confiance</span>
                    </div>
                    {item.earned_points !== null && item.max_points !== null ? <p>Résultat observé : <strong>{item.earned_points}/{item.max_points}</strong></p> : null}
                    {!isConfirmed ? (
                      <div className="rkjo-alignment-review">
                        <p>RKJO hésite sur cette compétence. Vérifie avant de continuer.</p>
                        <select value={selected} onChange={(e) => setCorrections((old) => ({...old,[item.question_ref]:e.target.value}))}>
                          <option value="">Choisir la bonne compétence</option>
                          {referential.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
                        </select>
                        <button type="button" disabled={!selected} onClick={() => setConfirmed((old) => ({...old,[item.question_ref]:true}))}>Confirmer</button>
                      </div>
                    ) : <small className="rkjo-confirmed-label">✓ Compris et vérifié</small>}
                  </div>
                </article>
              );
            })}
          </div>
          <div className="rkjo-next-step">
            <div><span>3</span><strong>Prochaine étape</strong><p>Ces observations alimenteront ton modèle d’apprentissage pour choisir le prochain exercice utile.</p></div>
            <button type="button" disabled={analysis.questions.some((q) => q.requires_confirmation && !confirmed[q.question_ref])}>Utiliser pour mon apprentissage →</button>
          </div>
        </section>
      ) : null}
    </EducationShell>
  );
}
