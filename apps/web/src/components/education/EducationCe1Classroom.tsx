"use client";

import Link from "next/link";
import { useState } from "react";

type Phase = "welcome" | "practice" | "proof" | "result";
type Message = { role: "teacher" | "learner"; text: string };
type Question = { left: number; right: number };
type Outcome = "passed" | "retry" | null;

const PRACTICE: Question = { left: 8, right: 5 };
const PROOF: Question = { left: 7, right: 6 };

function displayQuestion(question: Question) {
  return question.left + " + " + question.right + " = ?";
}

function makeInitialMessages(): Message[] {
  return [
    {
      role: "teacher",
      text: "Bonjour ! Je suis ton professeur de mathématiques. Aujourd'hui, nous allons apprendre à additionner en passant par 10.",
    },
    {
      role: "teacher",
      text: "Avec 8 + 5, on prend d'abord 2 dans les 5 pour arriver à 10. Il reste 3 à ajouter. Regarde le tableau, puis essaie !",
    },
  ];
}

export default function EducationCe1Classroom() {
  const [phase, setPhase] = useState<Phase>("welcome");
  const [messages, setMessages] = useState<Message[]>(makeInitialMessages);
  const [answer, setAnswer] = useState("");
  const [hintLevel, setHintLevel] = useState(0);
  const [practiceAttempts, setPracticeAttempts] = useState(0);
  const [proofAttempts, setProofAttempts] = useState(0);
  const [outcome, setOutcome] = useState<Outcome>(null);
  const [showBreakdown, setShowBreakdown] = useState(true);
  const [boardNotes, setBoardNotes] = useState("");

  const question = phase === "proof" || phase === "result" ? PROOF : PRACTICE;
  const hints = [
    "Commence par compléter 8 pour arriver à 10.",
    "Combien faut-il ajouter à 8 pour faire 10 ? Il faut 2.",
    "Sépare 5 en 2 et 3. Calcule d'abord 8 + 2, puis ajoute les 3 qui restent.",
  ];

  function say(text: string, studentText?: string) {
    setMessages((items) => [
      ...items,
      ...(studentText ? [{ role: "learner" as const, text: studentText }] : []),
      { role: "teacher", text },
    ]);
  }

  function startPractice() {
    setPhase("practice");
    setShowBreakdown(false);
    say("À toi ! Calcule 8 + 5. Tu peux me demander jusqu'à trois indices. Je ne donnerai pas la réponse directement.");
  }

  function requestHint() {
    if (phase !== "practice") return;
    if (hintLevel >= hints.length) {
      say("Tu as déjà reçu tous les indices. Regarde le tableau et propose une réponse.");
      return;
    }
    say(hints[hintLevel], "J'ai besoin d'un indice.");
    setHintLevel((value) => value + 1);
    setShowBreakdown(true);
  }

  function submit() {
    if (phase !== "practice" && phase !== "proof") return;
    const trimmed = answer.trim();
    if (!/^[0-9]{1,3}$/.test(trimmed)) {
      say("Écris un nombre entier positif pour que je puisse vérifier ton calcul.");
      return;
    }
    const value = Number(trimmed);
    setAnswer("");

    if (phase === "practice") {
      setPracticeAttempts((n) => n + 1);
      if (value !== PRACTICE.left + PRACTICE.right) {
        say("Pas encore ! Essaie de former 10 avec 8, puis ajoute le reste. Tu peux utiliser un indice.", trimmed);
        return;
      }
      say("Bravo pour cet entraînement ! Même avec des indices, ce n'est pas encore une preuve autonome. Essayons maintenant un nouveau calcul sans aide.", trimmed);
      setPhase("proof");
      setShowBreakdown(false);
      return;
    }

    setProofAttempts((n) => n + 1);
    const success = value === PROOF.left + PROOF.right;
    setOutcome(success ? "passed" : "retry");
    setPhase("result");
    say(
      success
        ? "Bravo ! Tu as réussi ce nouveau calcul sans indice. Cette preuve est réussie pour la démonstration."
        : "Merci d'avoir essayé ! Cette fois la preuve n'est pas réussie. Nous allons reprendre l'explication et nous entraîner de nouveau.",
      trimmed,
    );
  }

  function restart() {
    setPhase("welcome");
    setMessages(makeInitialMessages());
    setAnswer("");
    setHintLevel(0);
    setPracticeAttempts(0);
    setProofAttempts(0);
    setOutcome(null);
    setShowBreakdown(true);
    setBoardNotes("");
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-6 text-slate-900">
      <div className="mx-auto max-w-6xl space-y-5">
        <nav className="flex flex-wrap items-center justify-between gap-3 text-sm">
          <Link href="/education/lab" className="font-semibold text-blue-700 underline">← Retour au laboratoire</Link>
          <span className="rounded-full bg-amber-100 px-3 py-1 font-medium text-amber-900">Démonstration CE1 · sans IA connectée</span>
        </nav>

        <header className="rounded-2xl bg-slate-900 p-6 text-white">
          <p className="text-xs font-semibold uppercase tracking-widest text-cyan-300">RKJO Education · Classe interactive V1</p>
          <h1 className="mt-2 text-3xl font-bold">Apprendre les additions avec mon professeur</h1>
          <p className="mt-2 text-slate-200">Objectif : comprendre le passage par 10, essayer avec aide, puis démontrer son autonomie.</p>
          <p className="mt-2 text-sm text-amber-200">Séance locale scénarisée : aucune conversation IA, aucun micro, aucune donnée élève enregistrée.</p>
        </header>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
          <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5" aria-labelledby="board-title">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 id="board-title" className="text-xl font-bold">Tableau de la classe</h2>
                <p className="text-sm text-slate-600">Compte les jetons et décompose les nombres.</p>
              </div>
              <span className="rounded-full bg-sky-100 px-3 py-1 text-sm font-semibold text-sky-800">
                {phase === "welcome" ? "Explication" : phase === "practice" ? "Entraînement" : phase === "proof" ? "Preuve sans aide" : "Bilan"}
              </span>
            </div>
            <div className="rounded-xl bg-slate-950 p-5 text-white">
              <p className="text-sm text-slate-300">Calcul au tableau</p>
              <p className="my-3 text-center text-5xl font-bold tracking-wide" aria-label={displayQuestion(question)}>
                {question.left} <span className="text-cyan-300">+</span> {question.right} <span className="text-cyan-300">=</span> ?
              </p>
              <div className="space-y-3" aria-label="Représentation visuelle des deux nombres">
                <div className="flex flex-wrap gap-2">
                  {Array.from({ length: question.left }, (_, i) => <span key={"a" + i} className="h-7 w-7 rounded-full bg-cyan-400" aria-hidden="true" />)}
                </div>
                <div className="flex flex-wrap gap-2">
                  {Array.from({ length: question.right }, (_, i) => <span key={"b" + i} className="h-7 w-7 rounded-full bg-amber-400" aria-hidden="true" />)}
                </div>
              </div>
              <p className="mt-3 text-xs text-slate-300">Bleu : premier nombre · Jaune : second nombre</p>
            </div>

            {phase !== "proof" && phase !== "result" && (
              <div className="space-y-2">
                <button type="button" onClick={() => setShowBreakdown((v) => !v)} className="rounded-lg border border-blue-600 px-3 py-2 text-sm font-semibold text-blue-700">
                  {showBreakdown ? "Masquer" : "Voir"} la méthode du passage par 10
                </button>
                {showBreakdown && (
                  <div className="rounded-xl bg-blue-50 p-4 text-sm leading-7">
                    <p><strong>Étape 1 :</strong> 8 + 2 = 10.</p>
                    <p><strong>Étape 2 :</strong> 5 = 2 + 3.</p>
                    <p><strong>Étape 3 :</strong> 10 + 3 = 13.</p>
                    <p className="mt-2 text-blue-800">Les jetons permettent de voir les deux groupes.</p>
                  </div>
                )}
              </div>
            )}
            {phase === "proof" && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Pour cette preuve, la méthode et les indices restent masqués. Essaie seul.</p>}

            <div className="space-y-2">
              <label htmlFor="board-notes" className="block text-sm font-semibold">Mon brouillon</label>
              <textarea id="board-notes" value={boardNotes} onChange={(event) => setBoardNotes(event.target.value)}
                rows={3} placeholder="Tu peux écrire tes calculs ici..." className="w-full rounded-lg border border-slate-300 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-600" />
              <p className="text-xs text-slate-500">Ton brouillon reste dans cette page et n&apos;est pas corrigé automatiquement.</p>
            </div>
          </section>

          <section className="flex min-h-[540px] flex-col rounded-2xl border border-slate-200 bg-white p-5" aria-labelledby="teacher-title">
            <div className="flex items-center gap-3 border-b border-slate-100 pb-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-indigo-100 text-2xl" aria-hidden="true">👩‍🏫</div>
              <div>
                <h2 id="teacher-title" className="text-xl font-bold">Mon professeur</h2>
                <p className="text-sm text-slate-600">Explication guidée · démonstration locale</p>
              </div>
            </div>

            <div className="mt-4 max-h-[390px] flex-1 space-y-3 overflow-y-auto" role="log" aria-label="Échanges pédagogiques" aria-live="polite">
              {messages.map((message, i) => (
                <div key={i} className={"max-w-[95%] rounded-xl px-4 py-3 text-sm leading-6 " +
                  (message.role === "teacher" ? "bg-sky-50 text-slate-900" : "ml-auto bg-blue-700 text-white")}>
                  <p className="mb-1 text-xs font-semibold">{message.role === "teacher" ? "Professeur" : "Moi"}</p>
                  <p>{message.text}</p>
                </div>
              ))}
            </div>

            <div className="mt-5 space-y-3 border-t border-slate-100 pt-4">
              {phase === "welcome" && (
                <button type="button" onClick={startPractice} className="w-full rounded-xl bg-blue-700 px-5 py-3 font-semibold text-white">
                  J&apos;ai compris, je veux essayer
                </button>
              )}
              {(phase === "practice" || phase === "proof") && (
                <form onSubmit={(event) => { event.preventDefault(); submit(); }} className="space-y-3">
                  <label htmlFor="student-answer" className="block font-semibold">
                    {phase === "practice" ? "Entraînement : combien font 8 + 5 ?" : "Sans indice : combien font 7 + 6 ?"}
                  </label>
                  <input id="student-answer" inputMode="numeric" autoComplete="off" value={answer}
                    onChange={(event) => setAnswer(event.target.value)} placeholder="Ma réponse"
                    className="w-full rounded-xl border border-slate-300 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-600" />
                  <div className="flex flex-wrap gap-2">
                    <button type="submit" className="rounded-xl bg-blue-700 px-5 py-3 font-semibold text-white">Vérifier</button>
                    {phase === "practice" && (
                      <button type="button" onClick={requestHint} disabled={hintLevel >= hints.length}
                        className="rounded-xl border border-blue-700 px-5 py-3 font-semibold text-blue-700 disabled:cursor-not-allowed disabled:opacity-50">
                        {hintLevel >= hints.length ? "Indices utilisés" : "Demander un indice"}
                      </button>
                    )}
                  </div>
                </form>
              )}
              {phase === "result" && (
                <div className="space-y-3" role="status">
                  <p className="text-lg font-bold">{outcome === "passed" ? "Preuve autonome réussie" : "Encore un peu d'entraînement"}</p>
                  <p className="text-sm">Indices à l&apos;entraînement : {hintLevel} · Tentatives guidées : {practiceAttempts} · Tentatives autonomes : {proofAttempts}</p>
                  <p className="text-sm text-slate-600">Action recommandée : {outcome === "passed" ? "continuer avec une nouvelle addition" : "reprendre la méthode, puis refaire une preuve"}.</p>
                  <button type="button" onClick={restart} className="w-full rounded-xl bg-blue-700 px-5 py-3 font-semibold text-white">
                    Recommencer la séance
                  </button>
                </div>
              )}
              <p className="text-xs text-slate-500">Le dialogue est régi par des règles locales. La voix, l&apos;IA et la sauvegarde de progression viendront après intégration sécurisée.</p>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
