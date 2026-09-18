"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

type Progress = {
  completion_percent: number;
  competency_scores: Record<string, number>;
};

type TutorSource = {
  citation: number;
  document_id: string;
  chunk_id: string;
  score: number;
};

type TutorAnswer = {
  answer: string;
  level: string;
  completion_percent: number;
  weak_competencies: string[];
  sources: TutorSource[];
};

export default function EducationSession() {
  const searchParams = useSearchParams();

  const learnerId = searchParams.get("learnerId") ?? "";
  const courseId = searchParams.get("courseId") ?? "";

  const [progress, setProgress] = useState<Progress | null>(null);
  const [question, setQuestion] = useState("");
  const [tutor, setTutor] = useState<TutorAnswer | null>(null);
  const [loadingProgress, setLoadingProgress] = useState(
    Boolean(learnerId && courseId),
  );
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!learnerId || !courseId) {
      return;
    }

    let cancelled = false;

    async function loadProgress() {
      setLoadingProgress(true);
      setError("");

      try {
        const response = await fetch(
          `/api/education/learners/${encodeURIComponent(
            learnerId,
          )}/courses/${encodeURIComponent(courseId)}/progress`,
          { cache: "no-store" },
        );

        if (response.status === 404) {
          if (!cancelled) {
            setProgress({
              completion_percent: 0,
              competency_scores: {},
            });
          }
          return;
        }

        if (!response.ok) {
          throw new Error("Impossible de récupérer ta progression.");
        }

        const payload = (await response.json()) as Progress;

        if (!cancelled) {
          setProgress(payload);
        }
      } catch (cause) {
        if (!cancelled) {
          setError(
            cause instanceof Error
              ? cause.message
              : "Une erreur est survenue.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingProgress(false);
        }
      }
    }

    void loadProgress();

    return () => {
      cancelled = true;
    };
  }, [learnerId, courseId]);

  async function askTutor(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const normalizedQuestion = question.trim();

    if (!normalizedQuestion || !learnerId || !courseId) {
      return;
    }

    setAsking(true);
    setError("");

    try {
      const response = await fetch("/api/education/tutor", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          learner_id: learnerId,
          course_id: courseId,
          question: normalizedQuestion,
        }),
      });

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(
          payload.detail ?? "Le professeur IA ne peut pas répondre.",
        );
      }

      setTutor(payload as TutorAnswer);
      setQuestion("");
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Une erreur est survenue.",
      );
    } finally {
      setAsking(false);
    }
  }

  if (!learnerId || !courseId) {
    return (
      <main className="rkjo-session-page">
        <div className="rkjo-session-shell">
          <Link href="/education" className="rkjo-session-back">
            ← Aujourd&apos;hui
          </Link>

          <section className="rkjo-session-empty">
            <span>✦ RKJO Education</span>
            <h1>Préparons ta session</h1>
            <p>
              Aucun élève ou cours n&apos;est encore associé à cette
              session.
            </p>

            <Link href="/courses" className="rkjo-start">
              Choisir un cours
            </Link>
          </section>
        </div>
      </main>
    );
  }

  const completion =
    tutor?.completion_percent ??
    progress?.completion_percent ??
    0;

  const weakCompetencies =
    tutor?.weak_competencies ??
    Object.entries(progress?.competency_scores ?? {})
      .filter(([, score]) => score < 70)
      .map(([code]) => code)
      .sort();

  return (
    <main className="rkjo-session-page">
      <div className="rkjo-session-shell">
        <header className="rkjo-session-header">
          <div>
            <Link href="/education" className="rkjo-session-back">
              ← Aujourd&apos;hui
            </Link>

            <span className="rkjo-edu-kicker">
              SESSION PERSONNALISÉE
            </span>

            <h1>Ton professeur IA est prêt</h1>

            <p>
              RKJO adapte cette session à ta progression et aux
              compétences que tu dois renforcer.
            </p>
          </div>

          <div className="rkjo-session-score">
            <strong>
              {loadingProgress ? "…" : `${completion}%`}
            </strong>
            <span>progression</span>
          </div>
        </header>

        {error ? (
          <div className="rkjo-session-error">{error}</div>
        ) : null}

        <section className="rkjo-session-layout">
          <article className="rkjo-session-main">
            <span className="rkjo-edu-kicker">
              PROFESSEUR IA
            </span>

            <h2>
              {tutor
                ? "Continuons ensemble"
                : "Que veux-tu comprendre ?"}
            </h2>

            {tutor ? (
              <div className="rkjo-tutor-answer">
                <span className="rkjo-tutor-avatar">R</span>

                <div>
                  <strong>Professeur RKJO</strong>
                  <p>{tutor.answer}</p>

                  {tutor.sources.length > 0 ? (
                    <small>
                      Réponse appuyée sur{" "}
                      {tutor.sources.length} source
                      {tutor.sources.length > 1 ? "s" : ""}.
                    </small>
                  ) : null}
                </div>
              </div>
            ) : (
              <div className="rkjo-tutor-intro">
                <span>✦</span>
                <p>
                  Pose ta question. Je tiendrai compte de ton niveau,
                  de ta progression et des compétences que tu dois
                  renforcer.
                </p>
              </div>
            )}

            <form
              className="rkjo-tutor-form"
              onSubmit={askTutor}
            >
              <textarea
                value={question}
                onChange={(event) =>
                  setQuestion(event.target.value)
                }
                placeholder="Exemple : explique-moi cette notion étape par étape…"
                maxLength={4000}
                rows={4}
              />

              <button
                type="submit"
                className="rkjo-start"
                disabled={asking || !question.trim()}
              >
                {asking
                  ? "Le professeur réfléchit…"
                  : "Demander au professeur IA →"}
              </button>
            </form>
          </article>

          <aside className="rkjo-session-sidebar">
            <article>
              <span className="rkjo-edu-kicker">
                TA PROGRESSION
              </span>

              <strong className="rkjo-session-percent">
                {loadingProgress ? "…" : `${completion}%`}
              </strong>

              <div className="rkjo-progress">
                <i style={{ width: `${completion}%` }} />
              </div>
            </article>

            <article>
              <span className="rkjo-edu-kicker">
                À RENFORCER
              </span>

              {weakCompetencies.length > 0 ? (
                <ul className="rkjo-session-skills">
                  {weakCompetencies.map((competency) => (
                    <li key={competency}>
                      <span>↗</span>
                      {competency}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>
                  Aucune faiblesse identifiée pour le moment.
                </p>
              )}
            </article>

            {tutor?.level ? (
              <article>
                <span className="rkjo-edu-kicker">
                  ADAPTATION
                </span>
                <p>
                  Explications adaptées au niveau{" "}
                  <strong>{tutor.level}</strong>.
                </p>
              </article>
            ) : null}
          </aside>
        </section>
      </div>
    </main>
  );
}
