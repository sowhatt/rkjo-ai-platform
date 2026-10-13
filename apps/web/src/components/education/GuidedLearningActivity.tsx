"use client";

import { useState } from "react";

type LearningQuestion = {
  id: string;
  prompt: string;
  competency_code: string | null;
};

type Props = {
  courseTitle: string;
  subject: string;
  level: string;
  questions: LearningQuestion[];
};

export default function GuidedLearningActivity({
  courseTitle, subject, level, questions,
}: Props) {
  const [index, setIndex] = useState(0);
  const [response, setResponse] = useState("");
  const [reflection, setReflection] = useState("");
  const [stage, setStage] = useState<"explain" | "respond" | "reflect">("explain");

  const active = questions[index] ?? null;
  if (!active) return null;

  function next() {
    if (index >= questions.length - 1) return;
    setIndex((previous) => previous + 1);
    setResponse("");
    setReflection("");
    setStage("explain");
  }

  return (
    <section className="mt-6 rounded-2xl border border-blue-200 bg-white p-6" aria-labelledby="guided-learning-title">
      <span className="rkjo-edu-kicker">APPRENTISSAGE GUIDÉ · SANS NOTE</span>
      <h2 id="guided-learning-title" className="mt-2 text-xl font-bold">
        Comprendre et expliquer une notion
      </h2>
      <p className="mt-2 text-sm text-slate-600">
        {courseTitle} · {subject} · {level}
      </p>
      <p className="mt-3 text-sm text-slate-600">
        Étape {index + 1} sur {questions.length}. Cette activité sert à réfléchir :
        les réponses ne sont pas corrigées automatiquement et aucune maîtrise ne sera enregistrée.
      </p>
      <div className="mt-5 rounded-xl bg-blue-50 p-5">
        <p className="text-sm font-semibold text-blue-800">Objectif de compréhension</p>
        <p className="mt-2 font-semibold text-slate-900">
          {active.competency_code
            ? `Expliquer la compétence « ${active.competency_code} »`
            : "Expliquer la notion étudiée avec ses propres mots"}
        </p>
        <p className="mt-2 text-sm text-slate-700">
          Prérequis : relire le passage correspondant dans le cours avant de répondre.
          Les prérequis détaillés ne sont pas encore renseignés dans le catalogue.
        </p>
      </div>
      <div className="mt-5">
        <h3 className="text-lg font-bold">Question de compréhension</h3>
        <p className="mt-2 text-slate-800">{active.prompt}</p>
      </div>
      {stage === "explain" && (
        <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <h3 className="font-semibold">Méthode du professeur</h3>
          <p className="mt-2 text-sm text-slate-700">
            Repère les mots importants de la question, retrouve la notion dans ton support,
            puis essaie de l&apos;expliquer avec un exemple personnel. Ne cherche pas seulement
            une réponse à mémoriser : explique pourquoi elle est valable.
          </p>
          <button type="button" onClick={() => setStage("respond")}
            className="mt-4 rounded-xl bg-blue-900 px-4 py-3 font-semibold text-white">
            Je réponds à la question →
          </button>
        </div>
      )}
      {stage === "respond" && (
        <form className="mt-5" onSubmit={(event) => { event.preventDefault(); if (response.trim()) setStage("reflect"); }}>
          <label htmlFor="learning-response" className="block font-semibold">Ta réponse et ton raisonnement</label>
          <textarea id="learning-response" value={response} onChange={(event) => setResponse(event.target.value)}
            rows={4} maxLength={3000} className="mt-2 w-full rounded-xl border border-slate-300 p-3"
            placeholder="Écris ce que tu as compris, puis donne un exemple…" />
          <button type="submit" disabled={!response.trim()}
            className="mt-3 rounded-xl bg-blue-900 px-4 py-3 font-semibold text-white disabled:opacity-50">
            Relire et réfléchir à ma réponse →
          </button>
        </form>
      )}
      {stage === "reflect" && (
        <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-5">
          <h3 className="font-semibold">Retour guidé — autoévaluation</h3>
          <p className="mt-2 text-sm text-slate-700">
            Tu as formulé une réponse. Relis-la : as-tu défini les termes importants,
            justifié ton raisonnement et donné un exemple ? Ce retour ne valide pas
            l&apos;exactitude de ta réponse.
          </p>
          <label htmlFor="learning-reflection" className="mt-4 block font-semibold">
            Que modifierais-tu après avoir revu ton cours ?
          </label>
          <textarea id="learning-reflection" value={reflection}
            onChange={(event) => setReflection(event.target.value)} maxLength={3000} rows={3}
            className="mt-2 w-full rounded-xl border border-slate-300 p-3"
            placeholder="Je corrigerais… parce que…" />
          <div className="mt-4 flex flex-wrap gap-3">
            <button type="button" onClick={() => setStage("respond")}
              className="rounded-xl border border-blue-300 px-4 py-3 font-semibold text-blue-900">
              Refaire cette question
            </button>
            {index < questions.length - 1 && (
              <button type="button" onClick={next} disabled={!reflection.trim()}
                className="rounded-xl bg-blue-900 px-4 py-3 font-semibold text-white disabled:opacity-50">
                Question suivante →
              </button>
            )}
          </div>
          {index === questions.length - 1 && reflection.trim() && (
            <p className="mt-4 text-sm font-semibold text-emerald-900">
              Séquence guidée terminée. Pour vérifier la maîtrise, il faudra une évaluation autonome distincte.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
