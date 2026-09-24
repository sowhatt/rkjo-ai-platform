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
    context: "Licence 1 · Mathématiques",
    progress: 64,
    streak: "6 jours",
    time: "20 min",
    activityTitle: "Maîtriser les limites",
    activityText:
      "Revoir les limites remarquables puis résoudre 5 exercices progressifs.",
    recommendation:
      "Ton examen d’analyse approche. RKJO recommande de renforcer les limites aujourd’hui.",
    weakness: "Limites",
    weaknessScore: 54,
    mastered: "Dérivées",
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
              <Link href="/education/session" className="rkjo-start">
                ▶ Commencer ma session
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
