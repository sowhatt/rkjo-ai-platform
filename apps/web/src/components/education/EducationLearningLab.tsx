"use client";

import { useState } from "react";
import Link from "next/link";
import EducationDisciplinePicker, {
  type EducationDiscipline,
} from "@/components/education/EducationDisciplinePicker";

type Lesson = {
  title: string;
  objective: string;
  explanation: string;
  guidedQuestion: string;
  guidedAnswer: string;
  proofQuestion: string;
  proofAnswer: string;
  hint: string;
  check: (answer: string, expected: string) => boolean;
};

const norm = (value: string) =>
  value.trim().toLocaleLowerCase("fr").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\s+/g, " ");

const exact = (answer: string, expected: string) => norm(answer) === norm(expected);
const numeric = (answer: string, expected: string) =>
  answer.trim() !== "" && Number(answer.replace(",", ".")) === Number(expected);

const LESSONS: Record<EducationDiscipline, Lesson> = {
  mathematics: {
    title: "Résoudre une équation simple",
    objective: "Isoler l'inconnue et vérifier le résultat.",
    explanation: "Pour résoudre x + 5 = 12, soustrais 5 des deux côtés : x = 7. Vérifie : 7 + 5 = 12.",
    guidedQuestion: "Entraînement : résous x + 3 = 10. Combien vaut x ?",
    guidedAnswer: "7",
    proofQuestion: "Sans aide : résous x + 8 = 15. Combien vaut x ?",
    proofAnswer: "7",
    hint: "Soustrais le nombre ajouté à x des deux côtés.",
    check: numeric,
  },
  medicine: {
    title: "Le trajet du sang dans le cœur",
    objective: "Distinguer les circulations pulmonaire et systémique.",
    explanation: "Le ventricule droit envoie le sang vers les poumons. Le ventricule gauche l'envoie dans la circulation systémique. Ceci est un exercice académique, pas un avis clinique.",
    guidedQuestion: "Quel ventricule envoie le sang vers les poumons : droit ou gauche ?",
    guidedAnswer: "droit",
    proofQuestion: "Sans aide : quel ventricule propulse le sang dans la circulation systémique ?",
    proofAnswer: "gauche",
    hint: "Pense à la destination du sang et à la circulation pulmonaire.",
    check: exact,
  },
  biology: {
    title: "La mitose",
    objective: "Identifier une étape fondamentale de la division cellulaire.",
    explanation: "Pendant la métaphase, les chromosomes s'alignent au centre de la cellule. Pendant l'anaphase, les chromatides sœurs se séparent.",
    guidedQuestion: "Lors de quelle phase les chromosomes s'alignent-ils au centre ?",
    guidedAnswer: "metaphase",
    proofQuestion: "Sans aide : pendant quelle phase les chromatides sœurs se séparent-elles ?",
    proofAnswer: "anaphase",
    hint: "La métaphase vient après la prophase, avant la séparation.",
    check: exact,
  },
  general: {
    title: "Identifier l'idée principale",
    objective: "Distinguer une idée principale d'un détail.",
    explanation: "L'idée principale résume ce qu'un texte cherche surtout à nous apprendre. Un exemple est un détail qui l'illustre.",
    guidedQuestion: "Dans « Les arbres donnent de l'ombre. Par exemple, le chêne rafraîchit le jardin », l'idée principale parle-t-elle des arbres ou du jardin ?",
    guidedAnswer: "arbres",
    proofQuestion: "Sans aide : dans « Les abeilles pollinisent les fleurs. Ainsi, elles contribuent à la reproduction des plantes », quel insecte est le sujet principal ?",
    proofAnswer: "abeilles",
    hint: "Choisis le sujet commun à la première et à la deuxième phrase.",
    check: exact,
  },
};

type Stage = "explain" | "guided" | "proof" | "review";

export default function EducationLearningLab() {
  const [discipline, setDiscipline] = useState<EducationDiscipline>("mathematics");
  const [stage, setStage] = useState<Stage>("explain");
  const [answer, setAnswer] = useState("");
  const [hintUsed, setHintUsed] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [proofPassed, setProofPassed] = useState(false);
  const lesson = LESSONS[discipline];

  function reset(next: EducationDiscipline) {
    setDiscipline(next);
    setStage("explain");
    setAnswer("");
    setHintUsed(false);
    setFeedback("");
    setProofPassed(false);
  }

  function submitGuided() {
    if (!answer.trim()) {
      setFeedback("Saisis une réponse avant de continuer.");
      return;
    }
    if (!lesson.check(answer, lesson.guidedAnswer)) {
      setFeedback("Ce n'est pas encore correct. Relis l'explication et essaie de nouveau.");
      return;
    }
    setStage("proof");
    setFeedback("Bonne réponse. Passons maintenant à une question sans assistance.");
    setAnswer("");
  }

  function submitProof() {
    if (!answer.trim()) {
      setFeedback("Saisis une réponse avant de valider.");
      return;
    }
    const passed = lesson.check(answer, lesson.proofAnswer);
    setProofPassed(passed);
    setStage("review");
    setFeedback(passed ? "Preuve autonome réussie pour cette démonstration." : "La preuve autonome n'est pas réussie. Une révision est recommandée.");
    setAnswer("");
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900">
      <div className="mx-auto max-w-4xl space-y-6">
        <nav className="text-sm"><Link className="text-blue-700 underline" href="/education">← Accueil Education</Link></nav>
        <header className="rounded-2xl bg-slate-900 p-6 text-white">
          <p className="text-xs font-semibold uppercase tracking-wider text-cyan-300">RKJO Education · Démonstration locale</p>
          <h1 className="mt-2 text-3xl font-bold">Ma salle pédagogique</h1>
          <p className="mt-2 text-slate-200">Explore une leçon, entraîne-toi et vérifie tes acquis sans aide.</p>
          <p className="mt-3 text-sm text-amber-200">Mode démonstration : exercices prédéfinis, aucune IA appelée, aucune progression enregistrée.</p>
        </header>
        <section className="rounded-2xl border border-slate-200 bg-white p-5">
          <EducationDisciplinePicker value={discipline} onChange={reset} />
        </section>
        <section className="rounded-2xl border border-slate-200 bg-white p-6" aria-live="polite">
          <div className="mb-4 flex flex-wrap gap-2 text-xs font-medium">
            {(["explain", "guided", "proof", "review"] as Stage[]).map((step, i) => (
              <span key={step} className={`rounded-full px-3 py-1 ${step === stage ? "bg-blue-700 text-white" : "bg-slate-100 text-slate-500"}`}>
                {i + 1}. {["Comprendre", "S'entraîner", "Sans aide", "Bilan"][i]}
              </span>
            ))}
          </div>
          <h2 className="text-2xl font-bold">{lesson.title}</h2>
          <p className="mt-2 text-sm text-slate-600"><strong>Objectif :</strong> {lesson.objective}</p>
          {stage === "explain" && (
            <div className="mt-5 space-y-4">
              <p className="rounded-xl bg-sky-50 p-4 leading-7">{lesson.explanation}</p>
              <button type="button" onClick={() => { setStage("guided"); setFeedback(""); }} className="rounded-lg bg-blue-700 px-5 py-3 font-semibold text-white">Commencer l'exercice</button>
            </div>
          )}
          {(stage === "guided" || stage === "proof") && (
            <form className="mt-5 space-y-4" onSubmit={(event) => { event.preventDefault(); if (stage === "guided") submitGuided(); else submitProof(); }}>
              <label htmlFor="lab-answer" className="block font-medium">{stage === "guided" ? lesson.guidedQuestion : lesson.proofQuestion}</label>
              <input id="lab-answer" autoComplete="off" value={answer} onChange={(event) => setAnswer(event.target.value)} className="w-full rounded-lg border border-slate-300 p-3 focus:outline-none focus:ring-2 focus:ring-blue-600" placeholder="Écris ta réponse" />
              {stage === "guided" && (
                <div className="space-y-2">
                  <button type="button" onClick={() => setHintUsed(true)} className="rounded-lg border border-blue-700 px-4 py-2 font-medium text-blue-700">Demander un indice</button>
                  {hintUsed && <p className="rounded-lg bg-amber-50 p-3 text-sm">Indice : {lesson.hint}</p>}
                </div>
              )}
              {stage === "proof" && <p className="text-sm text-slate-600">Aucun indice disponible : cette étape vérifie une réponse autonome.</p>}
              <button type="submit" className="block rounded-lg bg-blue-700 px-5 py-3 font-semibold text-white">Valider ma réponse</button>
            </form>
          )}
          {feedback && <p role="status" className="mt-4 rounded-lg bg-slate-100 p-3 text-sm">{feedback}</p>}
          {stage === "review" && (
            <div className="mt-5 space-y-4">
              <p className="font-semibold">{proofPassed ? "Objectif démonstration atteint" : "Une nouvelle tentative est recommandée"}</p>
              <p className="text-sm text-slate-600">Indice utilisé à l'entraînement : {hintUsed ? "oui" : "non"}. Résultat de la preuve autonome : {proofPassed ? "réussi" : "à retravailler"}.</p>
              <p className="text-sm text-slate-600">Prochaine activité suggérée : {proofPassed ? "aborder une nouvelle notion" : "revoir l'explication et refaire un exercice"}.</p>
              <button type="button" onClick={() => reset(discipline)} className="rounded-lg bg-blue-700 px-5 py-3 font-semibold text-white">Recommencer la leçon</button>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
