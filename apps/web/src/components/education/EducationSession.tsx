"use client";

import Link from "next/link";
import {
  FormEvent,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useSearchParams } from "next/navigation";

type Progress = {
  completion_percent: number;
  competency_scores: Record<string, number>;
};

type LearnerQuestion = {
  id: string;
  prompt: string;
  points: number;
  competency_code: string | null;
};

type LearnerAssessment = {
  id: string;
  course_id: string;
  title: string;
  questions: LearnerQuestion[];
};

type Attempt = {
  id: string;
  assessment_id: string;
  learner_id: string;
  status: string;
  score: number;
  max_score: number;
  percentage: number;
};

type LearningResult = {
  question_id: string;
  competency_code: string;
  correct: boolean;
  autonomy_score: number;
  independently_correct: boolean;
  mastery: string;
  proof_required: boolean;
  proof_challenge_id: string | null;
};

type AttemptResult = Attempt & {
  learning: LearningResult[];
};

type ProofChallenge = {
  id: string;
  competency_code: string;
  prompt: string;
  status: string;
};

type ProofResult = {
  status: string;
  competency_code: string;
  independently_verified: boolean;
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

function masteryLabel(value: string) {
  switch (value) {
    case "mastered":
      return "Maîtrisée";
    case "provisional":
      return "À confirmer";
    case "developing":
      return "En développement";
    case "not_demonstrated":
      return "Non démontrée";
    default:
      return value;
  }
}

export default function EducationSession() {
  const searchParams = useSearchParams();

  const learnerId = searchParams.get("learnerId") ?? "";
  const courseId = searchParams.get("courseId") ?? "";

  const [progress, setProgress] =
    useState<Progress | null>(null);

  const [assessments, setAssessments] =
    useState<LearnerAssessment[]>([]);

  const [assessmentIndex, setAssessmentIndex] =
    useState(0);

  const [questionIndex, setQuestionIndex] =
    useState(0);

  const [attempt, setAttempt] =
    useState<Attempt | null>(null);

  const [answer, setAnswer] =
    useState("");

  const [hintsUsed, setHintsUsed] =
    useState(0);

  const [assistanceLevel, setAssistanceLevel] =
    useState(0);

  const [attemptCount, setAttemptCount] =
    useState(1);

  const [result, setResult] =
    useState<AttemptResult | null>(null);

  const [proof, setProof] =
    useState<ProofChallenge | null>(null);

  const [proofAnswer, setProofAnswer] =
    useState("");

  const [proofResult, setProofResult] =
    useState<ProofResult | null>(null);

  const [question, setQuestion] =
    useState("");

  const [tutor, setTutor] =
    useState<TutorAnswer | null>(null);

  const [loadingProgress, setLoadingProgress] =
    useState(Boolean(learnerId && courseId));

  const [loadingActivity, setLoadingActivity] =
    useState(Boolean(learnerId && courseId));

  const [startingAttempt, setStartingAttempt] =
    useState(false);

  const [submitting, setSubmitting] =
    useState(false);

  const [loadingProof, setLoadingProof] =
    useState(false);

  const [submittingProof, setSubmittingProof] =
    useState(false);

  const [asking, setAsking] =
    useState(false);

  const [error, setError] =
    useState("");

  const assessment =
    assessments[assessmentIndex] ?? null;

  const currentQuestion =
    assessment?.questions[questionIndex] ?? null;

  const currentLearning = useMemo(() => {
    if (!result || !currentQuestion) {
      return null;
    }

    return (
      result.learning.find(
        (item) =>
          item.question_id === currentQuestion.id,
      ) ?? null
    );
  }, [result, currentQuestion]);

  useEffect(() => {
    if (!learnerId || !courseId) {
      return;
    }

    let cancelled = false;

    async function loadProgress() {
      setLoadingProgress(true);

      try {
        const response = await fetch(
          `/api/education/learners/${encodeURIComponent(
            learnerId,
          )}/courses/${encodeURIComponent(
            courseId,
          )}/progress`,
          {
            cache: "no-store",
          },
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
          throw new Error(
            "Impossible de récupérer ta progression.",
          );
        }

        const payload =
          (await response.json()) as Progress;

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

  useEffect(() => {
    if (!learnerId || !courseId) {
      return;
    }

    let cancelled = false;

    async function loadAssessments() {
      setLoadingActivity(true);
      setError("");

      try {
        const response = await fetch(
          `/api/education/courses/${encodeURIComponent(
            courseId,
          )}/assessments`,
          {
            cache: "no-store",
          },
        );

        const payload = await response.json();

        if (!response.ok) {
          throw new Error(
            payload.detail ??
              "Impossible de charger les exercices.",
          );
        }

        if (!cancelled) {
          setAssessments(
            payload as LearnerAssessment[],
          );
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
          setLoadingActivity(false);
        }
      }
    }

    void loadAssessments();

    return () => {
      cancelled = true;
    };
  }, [learnerId, courseId]);

  async function ensureAttempt() {
    if (attempt) {
      return attempt;
    }

    if (!assessment) {
      throw new Error(
        "Aucune activité disponible.",
      );
    }

    setStartingAttempt(true);

    try {
      const response = await fetch(
        "/api/education/attempts",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            assessment_id: assessment.id,
            learner_id: learnerId,
          }),
        },
      );

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(
          payload.detail ??
            "Impossible de démarrer l'exercice.",
        );
      }

      const created = payload as Attempt;
      setAttempt(created);

      return created;
    } finally {
      setStartingAttempt(false);
    }
  }

  async function submitExercise(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (
      !assessment ||
      !currentQuestion ||
      !answer.trim()
    ) {
      return;
    }

    setSubmitting(true);
    setError("");

    try {
      const activeAttempt =
        await ensureAttempt();

      const response = await fetch(
        `/api/education/attempts/${encodeURIComponent(
          activeAttempt.id,
        )}/submit`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            answers: {
              [currentQuestion.id]:
                answer.trim(),
            },
            evidence: {
              [currentQuestion.id]: {
                assistance_level:
                  assistanceLevel,
                hints_used: hintsUsed,
                attempt_count: attemptCount,
              },
            },
          }),
        },
      );

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(
          payload.detail ??
            "Impossible de valider ta réponse.",
        );
      }

      const submitted =
        payload as AttemptResult;

      setResult(submitted);

      const learning =
        submitted.learning.find(
          (item) =>
            item.question_id ===
            currentQuestion.id,
        );

      if (learning?.proof_challenge_id) {
        await loadProof(
          learning.proof_challenge_id,
        );
      }
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Une erreur est survenue.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function loadProof(
    challengeId: string,
  ) {
    setLoadingProof(true);

    try {
      const response = await fetch(
        `/api/education/proof-challenges/${encodeURIComponent(
          challengeId,
        )}`,
        {
          cache: "no-store",
        },
      );

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(
          payload.detail ??
            "Impossible de charger la vérification.",
        );
      }

      setProof(payload as ProofChallenge);
    } finally {
      setLoadingProof(false);
    }
  }

  async function submitProof(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!proof || !proofAnswer.trim()) {
      return;
    }

    setSubmittingProof(true);
    setError("");

    try {
      const response = await fetch(
        `/api/education/proof-challenges/${encodeURIComponent(
          proof.id,
        )}/submit`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            answer: proofAnswer.trim(),
          }),
        },
      );

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(
          payload.detail ??
            "Impossible de vérifier ton apprentissage.",
        );
      }

      setProofResult(payload as ProofResult);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Une erreur est survenue.",
      );
    } finally {
      setSubmittingProof(false);
    }
  }

  async function askTutor(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    const normalizedQuestion =
      question.trim();

    if (
      !normalizedQuestion ||
      !learnerId ||
      !courseId
    ) {
      return;
    }

    setAsking(true);
    setError("");

    try {
      const response = await fetch(
        "/api/education/tutor",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            learner_id: learnerId,
            course_id: courseId,
            question: normalizedQuestion,
          }),
        },
      );

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(
          payload.detail ??
            "Le professeur IA ne peut pas répondre.",
        );
      }

      setTutor(payload as TutorAnswer);
      setQuestion("");
      setHintsUsed((value) => value + 1);
      setAssistanceLevel((value) =>
        Math.max(value, 3),
      );
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

  function requestHint() {
    setHintsUsed((value) => value + 1);
    setAssistanceLevel((value) =>
      Math.max(value, 2),
    );
  }

  if (!learnerId || !courseId) {
    return (
      <main className="rkjo-session-page">
        <div className="rkjo-session-shell">
          <Link
            href="/education"
            className="rkjo-session-back"
          >
            ← Aujourd&apos;hui
          </Link>

          <section className="rkjo-session-empty">
            <span>✦ RKJO Education</span>
            <h1>Préparons ta session</h1>
            <p>
              Aucun élève ou cours
              n&apos;est encore associé à
              cette session.
            </p>

            <Link
              href="/education/courses"
              className="rkjo-start"
            >
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
    Object.entries(
      progress?.competency_scores ?? {},
    )
      .filter(([, score]) => score < 70)
      .map(([code]) => code)
      .sort();

  return (
    <main className="rkjo-session-page">
      <div className="rkjo-session-shell">
        <header className="rkjo-session-header">
          <div>
            <Link
              href="/education"
              className="rkjo-session-back"
            >
              ← Aujourd&apos;hui
            </Link>

            <span className="rkjo-edu-kicker">
              SESSION D&apos;APPRENTISSAGE
            </span>

            <h1>
              Apprends, essaie, puis prouve
              que tu sais faire
            </h1>

            <p>
              RKJO mesure ta réussite mais
              aussi ton niveau d&apos;autonomie.
            </p>
          </div>

          <div className="rkjo-session-score">
            <strong>
              {loadingProgress
                ? "…"
                : `${completion}%`}
            </strong>
            <span>progression</span>
          </div>
        </header>

        {error ? (
          <div className="rkjo-session-error">
            {error}
          </div>
        ) : null}

        <section className="rkjo-session-layout">
          <div className="rkjo-learning-column">
            <article className="rkjo-session-main">
              <span className="rkjo-edu-kicker">
                TA PROCHAINE ACTIVITÉ
              </span>

              {loadingActivity ? (
                <div className="rkjo-activity-state">
                  Chargement de ton exercice…
                </div>
              ) : !assessment ||
                !currentQuestion ? (
                <div className="rkjo-activity-state">
                  <h2>
                    Aucun exercice disponible
                  </h2>
                  <p>
                    Le cours est prêt, mais
                    aucune évaluation ne lui
                    est encore associée.
                  </p>
                </div>
              ) : (
                <>
                  <div className="rkjo-exercise-head">
                    <div>
                      <h2>
                        {assessment.title}
                      </h2>

                      <p>
                        Question{" "}
                        {questionIndex + 1} /{" "}
                        {
                          assessment.questions
                            .length
                        }
                      </p>
                    </div>

                    {currentQuestion.competency_code ? (
                      <span className="rkjo-competency-badge">
                        {
                          currentQuestion.competency_code
                        }
                      </span>
                    ) : null}
                  </div>

                  <div className="rkjo-question-card">
                    <strong>
                      {currentQuestion.prompt}
                    </strong>
                  </div>

                  {!result ? (
                    <form
                      className="rkjo-exercise-form"
                      onSubmit={submitExercise}
                    >
                      <input
                        value={answer}
                        onChange={(event) => {
                          setAnswer(
                            event.target.value,
                          );
                          setAttemptCount(
                            (value) =>
                              Math.max(value, 1),
                          );
                        }}
                        placeholder="Ta réponse"
                        autoComplete="off"
                      />

                      <div className="rkjo-help-row">
                        <button
                          type="button"
                          onClick={requestHint}
                        >
                          💡 Un indice
                        </button>

                        <span>
                          Aides utilisées :{" "}
                          {hintsUsed}
                        </span>
                      </div>

                      {hintsUsed > 0 ? (
                        <div className="rkjo-hint">
                          Essaie de décomposer
                          le problème en petites
                          étapes avant de
                          calculer.
                        </div>
                      ) : null}

                      <button
                        type="submit"
                        className="rkjo-action-primary"
                        disabled={
                          submitting ||
                          startingAttempt ||
                          !answer.trim()
                        }
                      >
                        {submitting ||
                        startingAttempt
                          ? "Validation…"
                          : "Valider ma réponse"}
                      </button>
                    </form>
                  ) : currentLearning ? (
                    <div className="rkjo-learning-result">
                      <div
                        className={
                          currentLearning.correct
                            ? "rkjo-result-banner success"
                            : "rkjo-result-banner warning"
                        }
                      >
                        <strong>
                          {currentLearning.correct
                            ? "✓ Bonne réponse"
                            : "À retravailler"}
                        </strong>
                      </div>

                      <div className="rkjo-result-grid">
                        <div>
                          <span>Score</span>
                          <strong>
                            {result.score} /{" "}
                            {result.max_score}
                          </strong>
                        </div>

                        <div>
                          <span>Autonomie</span>
                          <strong>
                            {
                              currentLearning.autonomy_score
                            }
                            %
                          </strong>
                        </div>

                        <div>
                          <span>
                            Compétence
                          </span>
                          <strong>
                            {masteryLabel(
                              currentLearning.mastery,
                            )}
                          </strong>
                        </div>
                      </div>

                      {currentLearning.proof_required ? (
                        <div className="rkjo-proof-intro">
                          <strong>
                            Vérifions maintenant
                            ton apprentissage.
                          </strong>
                          <p>
                            Tu vas résoudre une
                            nouvelle question sans
                            aide de RKJO.
                          </p>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </>
              )}
            </article>

            {proof &&
            currentLearning?.proof_required ? (
              <article className="rkjo-session-main rkjo-proof-card">
                <span className="rkjo-edu-kicker">
                  VÉRIFICATION EN AUTONOMIE
                </span>

                <h2>
                  Cette fois, sans indice
                </h2>

                <p>
                  RKJO veut vérifier que tu
                  sais refaire seul.
                </p>

                <div className="rkjo-question-card">
                  <strong>
                    {proof.prompt}
                  </strong>
                </div>

                {!proofResult ? (
                  <form
                    className="rkjo-exercise-form"
                    onSubmit={submitProof}
                  >
                    <input
                      value={proofAnswer}
                      onChange={(event) =>
                        setProofAnswer(
                          event.target.value,
                        )
                      }
                      placeholder="Ta réponse"
                      autoComplete="off"
                    />

                    <button
                      type="submit"
                      className="rkjo-action-primary"
                      disabled={
                        submittingProof ||
                        !proofAnswer.trim()
                      }
                    >
                      {submittingProof
                        ? "Vérification…"
                        : "Valider sans aide"}
                    </button>
                  </form>
                ) : (
                  <div
                    className={
                      proofResult.independently_verified
                        ? "rkjo-proof-final success"
                        : "rkjo-proof-final warning"
                    }
                  >
                    <strong>
                      {proofResult.independently_verified
                        ? "✓ Compétence vérifiée en autonomie"
                        : "Compétence à renforcer"}
                    </strong>

                    <p>
                      {proofResult.independently_verified
                        ? "Tu as réussi une nouvelle question sans aide."
                        : "RKJO adaptera les prochains exercices pour consolider cette compétence."}
                    </p>
                  </div>
                )}
              </article>
            ) : null}

            {loadingProof ? (
              <article className="rkjo-session-main">
                Préparation de la vérification…
              </article>
            ) : null}

            <article className="rkjo-session-main">
              <span className="rkjo-edu-kicker">
                PROFESSEUR RKJO
              </span>

              <h2>
                Besoin de comprendre avant
                de répondre ?
              </h2>

              {tutor ? (
                <div className="rkjo-tutor-answer">
                  <span className="rkjo-tutor-avatar">
                    R
                  </span>

                  <div>
                    <strong>
                      Professeur RKJO
                    </strong>
                    <p>{tutor.answer}</p>
                  </div>
                </div>
              ) : (
                <div className="rkjo-tutor-intro">
                  <span>✦</span>
                  <p>
                    Je peux t&apos;aider. Les
                    aides utilisées sont prises
                    en compte dans ton score
                    d&apos;autonomie.
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
                    setQuestion(
                      event.target.value,
                    )
                  }
                  placeholder="Demande une explication ou un indice…"
                  maxLength={4000}
                  rows={3}
                  disabled={Boolean(proof)}
                />

                <button
                  type="submit"
                  className="rkjo-start"
                  disabled={
                    asking ||
                    !question.trim() ||
                    Boolean(proof)
                  }
                >
                  {asking
                    ? "Le professeur réfléchit…"
                    : "Demander de l'aide →"}
                </button>
              </form>

              {proof ? (
                <small className="rkjo-proof-lock">
                  🔒 Le professeur est désactivé
                  pendant la vérification en
                  autonomie.
                </small>
              ) : null}
            </article>
          </div>

          <aside className="rkjo-session-sidebar">
            <article>
              <span className="rkjo-edu-kicker">
                TA PROGRESSION
              </span>

              <strong className="rkjo-session-percent">
                {loadingProgress
                  ? "…"
                  : `${completion}%`}
              </strong>

              <div className="rkjo-progress">
                <i
                  style={{
                    width: `${completion}%`,
                  }}
                />
              </div>
            </article>

            {currentLearning ? (
              <article>
                <span className="rkjo-edu-kicker">
                  AUTONOMIE
                </span>

                <strong className="rkjo-session-percent">
                  {
                    currentLearning.autonomy_score
                  }
                  %
                </strong>

                <p>
                  {currentLearning.independently_correct
                    ? "Réussite indépendante."
                    : "RKJO distingue la réussite de l'autonomie."}
                </p>
              </article>
            ) : null}

            <article>
              <span className="rkjo-edu-kicker">
                À RENFORCER
              </span>

              {weakCompetencies.length > 0 ? (
                <ul className="rkjo-session-skills">
                  {weakCompetencies.map(
                    (competency) => (
                      <li key={competency}>
                        <span>↗</span>
                        {competency}
                      </li>
                    ),
                  )}
                </ul>
              ) : (
                <p>
                  Aucune faiblesse identifiée
                  pour le moment.
                </p>
              )}
            </article>
          </aside>
        </section>
      </div>
    </main>
  );
}
