"use client";

import Link from "next/link";
import { useState } from "react";

type Experience = "learner" | "student";

type ExperienceProfile = {
  label: string;
  initials: string;
  greeting: string;
  context: string;
  progress: number;
  streak: string;
  time: string;
  activityTitle: string;
  activityText: string;
  recommendation: string;
  weakness: string;
  weaknessScore: number;
  mastered: string;
  masteredScore: number;
};

const experiences: Record<Experience, ExperienceProfile> = {
  learner: {
    label: "Élève",
    initials: "EM",
    greeting: "Bonjour Emma 👋",
    context: "Mathématiques · CE1",
    progress: 68,
    streak: "4 jours",
    time: "15 min",
    activityTitle: "Dizaines et unités",
    activityText:
      "Comprendre comment décomposer un nombre en dizaines et unités.",
    recommendation:
      "Continue ta leçon pour consolider ce que tu as appris hier.",
    weakness: "Additions avec retenue",
    weaknessScore: 52,
    mastered: "Nombres jusqu’à 100",
    masteredScore: 86,
  },
  student: {
    label: "Étudiant",
    initials: "SA",
    greeting: "Bonjour Sarah 👋",
    context: "Études de santé · Médecine, pharmacie, soins infirmiers",
    progress: 64,
    streak: "6 jours",
    time: "20 min",
    activityTitle: "Réviser mes cours de santé",
    activityText:
      "Retrouve tes CM, TD et TP et organise tes prochaines révisions.",
    recommendation:
      "Commence par tes supports de cours, puis entraîne-toi avec des fiches, flashcards et QCM.",
    weakness: "Notions à renforcer",
    weaknessScore: 54,
    mastered: "Notions révisées",
    masteredScore: 82,
  },
};

export default function EducationHome() {
  const [experience, setExperience] =
    useState<Experience>("student");

  const profile = experiences[experience];

  return (
    <div className="rkjo-edu-app">
      <aside className="rkjo-edu-side">
        <Link href="/education" className="rkjo-edu-brand">
          <span className="rkjo-edu-mark">R</span>

          <span>
            <strong>RKJO</strong>
            <small>Education</small>
          </span>
        </Link>

        <nav className="rkjo-edu-navigation">
          <Link className="active" href="/education">
            <span>⌂</span>
            Aujourd&apos;hui
          </Link>

          <Link href="/education/courses">
            <span>▤</span>
            Mes cours
          </Link>

          <Link href="/education/tutor">
            <span>✦</span>
            Professeur IA
          </Link>

          <Link href="/education/resources">
            <span>□</span>
            Ressources
          </Link>

          <Link href="/education/progress">
            <span>◫</span>
            Progression
          </Link>
        </nav>

        <div className="rkjo-edu-profile">
          <span className="rkjo-edu-avatar">
            {profile.initials}
          </span>

          <span>
            <strong>{profile.label}</strong>
            <small>Profil démonstration</small>
          </span>
        </div>
      </aside>

      <main className="rkjo-edu-content">
        <header className="rkjo-edu-topbar">
          <div>
            <span className="rkjo-edu-kicker">
              AUJOURD&apos;HUI
            </span>

            <h1>{profile.greeting}</h1>
            <p>{profile.context}</p>
          </div>

          <div
            className="rkjo-edu-switch"
            aria-label="Choisir l’expérience"
          >
            <button
              type="button"
              className={
                experience === "learner" ? "active" : ""
              }
              onClick={() => setExperience("learner")}
            >
              🎒 Élève
            </button>

            <button
              type="button"
              className={
                experience === "student" ? "active" : ""
              }
              onClick={() => setExperience("student")}
            >
              🎓 Étudiant
            </button>
          </div>
        </header>

        <section className="rkjo-edu-summary">
          <article>
            <span>Progression</span>
            <strong>{profile.progress}%</strong>

            <div className="rkjo-progress">
              <i style={{ width: `${profile.progress}%` }} />
            </div>
          </article>

          <article>
            <span>Régularité</span>
            <strong>{profile.streak}</strong>
            <small>🔥 Continue comme ça</small>
          </article>

          <article>
            <span>Session recommandée</span>
            <strong>{profile.time}</strong>
            <small>Adaptée à ton niveau</small>
          </article>
        </section>

        <section className="rkjo-today-card">
          <div className="rkjo-today-copy">
            <span className="rkjo-edu-kicker">
              TA PROCHAINE ACTIVITÉ
            </span>

            <h2>{profile.activityTitle}</h2>

            <p>{profile.activityText}</p>

            <div className="rkjo-ai-recommendation">
              <span>✦</span>

              <p>
                <strong>Recommandation RKJO</strong>
                {profile.recommendation}
              </p>
            </div>

            <div className="rkjo-today-actions">
              <Link href="/education/courses" className="rkjo-start">
                ▶ Choisir un cours pour commencer
              </Link>

              <Link href="/education/tutor" className="rkjo-ask">
                Demander au professeur IA
              </Link>
            </div>
          </div>

          <div className="rkjo-session-visual">
            <div className="rkjo-session-ring">
              <strong>{profile.time}</strong>
              <span>aujourd&apos;hui</span>
            </div>
          </div>
        </section>

        <section aria-labelledby="rkjo-revision-heading" className="mt-10">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
            <div>
              <span className="rkjo-edu-kicker">TON ESPACE DE RÉVISION</span>
              <h2 id="rkjo-revision-heading" className="mt-2 text-2xl font-bold">
                Apprends à partir de tes cours
              </h2>
              <p className="mt-2 text-sm text-slate-600">
                CM, TD et TP : retrouve tes supports et découvre les outils de révision RKJO.
              </p>
            </div>
            <Link href="/education/resources" className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50">
              Mes documents →
            </Link>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {[
              {slug:"fiches",icon:"📑",title:"Fiches de révision",detail:"Synthèses, définitions, tableaux et notes essentielles.",tone:"from-blue-100 to-sky-50",visual:"Résumé de cours"},
              {slug:"cartes",icon:"🧠",title:"Cartes mentales",detail:"Notions, liens, mécanismes et prérequis organisés.",tone:"from-violet-100 to-fuchsia-50",visual:"Concept → branches"},
              {slug:"flashcards",icon:"🗂️",title:"Flashcards",detail:"Questions courtes et mémorisation espacée.",tone:"from-amber-100 to-yellow-50",visual:"Question ↔ réponse"},
              {slug:"qcm",icon:"✅",title:"QCM et exercices",detail:"Entraîne-toi sur les thèmes de tes cours et TD.",tone:"from-emerald-100 to-teal-50",visual:"Choisis ta réponse"},
              {slug:"examens",icon:"🎓",title:"Examens blancs",detail:"Prépare tes partiels avec des évaluations sans aide.",tone:"from-rose-100 to-orange-50",visual:"Simulation d'examen"},
            ].map((tool) => (
              <Link
                key={tool.slug}
                href={`/education/study-tools#${tool.slug}`}
                className="group overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
              >
                <div className={`relative flex h-36 items-center justify-center overflow-hidden bg-gradient-to-br ${tool.tone}`} aria-hidden="true">
                  <div className="absolute left-5 top-5 h-14 w-11 -rotate-12 rounded-lg border border-white/80 bg-white/70 shadow-sm" />
                  <div className="absolute right-7 bottom-5 h-16 w-14 rotate-12 rounded-lg border border-white/80 bg-white/70 shadow-sm" />
                  <div className="relative flex flex-col items-center gap-2 rounded-2xl border border-white/80 bg-white/90 px-7 py-4 shadow-md">
                    <span className="text-4xl">{tool.icon}</span>
                    <span className="text-xs font-semibold text-slate-600">{tool.visual}</span>
                  </div>
                </div>
                <div className="p-5">
                  <h3 className="font-bold text-slate-900">{tool.title} <span className="float-right text-slate-400 transition group-hover:translate-x-1">→</span></h3>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{tool.detail}</p>
                </div>
              </Link>
            ))}
          </div>
          <p className="mt-3 text-xs text-slate-500">
            Présentation des outils : la génération automatique à partir des documents sera raccordée progressivement.
          </p>
        </section>

        <section className="rkjo-learning-grid">
          <div>
            <span className="rkjo-edu-kicker">
              TON APPRENTISSAGE
            </span>

            <h2>Où en es-tu ?</h2>

            <div className="rkjo-skill-list">
              <article>
                <div>
                  <span className="rkjo-skill-icon warning">
                    ↗
                  </span>

                  <div>
                    <strong>{profile.weakness}</strong>
                    <small>À renforcer</small>
                  </div>
                </div>

                <b>{profile.weaknessScore}%</b>
              </article>

              <article>
                <div>
                  <span className="rkjo-skill-icon success">
                    ✓
                  </span>

                  <div>
                    <strong>{profile.mastered}</strong>
                    <small>Bien maîtrisé</small>
                  </div>
                </div>

                <b>{profile.masteredScore}%</b>
              </article>
            </div>
          </div>

          <aside className="rkjo-professor-card">
            <span className="rkjo-professor-avatar">
              ✦
            </span>

            <span className="rkjo-edu-kicker">
              PROFESSEUR RKJO
            </span>

            <h2>Besoin d&apos;une explication ?</h2>

            <p>
              Ton professeur connaît tes ressources et
              peut t&apos;aider à comprendre sans simplement
              te donner la réponse.
            </p>

            <Link href="/education/tutor">
              Parler à mon professeur →
            </Link>
          </aside>
        </section>
      </main>

      <nav className="rkjo-mobile-nav">
        <Link className="active" href="/education">
          <span>⌂</span>
          Aujourd&apos;hui
        </Link>

        <Link href="/education/courses">
          <span>▤</span>
          Cours
        </Link>

        <Link href="/education/tutor">
          <span>✦</span>
          Professeur
        </Link>

        <Link href="/education/progress">
          <span>◫</span>
          Progrès
        </Link>
      </nav>
    </div>
  );
}
