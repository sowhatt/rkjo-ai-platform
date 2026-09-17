"use client";

import {
  useEffect,
  useState,
} from "react";

import Link from "next/link";
import { useParams } from "next/navigation";

type Course = {
  course_id: string;
  title: string;
  subject: string;
  level: string;
  curriculum_id: string | null;
  document_ids: string[];
};

export default function CourseDetailPage() {
  const params = useParams<{
    courseId: string;
  }>();

  const courseId = params.courseId;

  const [course, setCourse] =
    useState<Course | null>(null);

  const [loading, setLoading] =
    useState(true);

  const [showResourceModal, setShowResourceModal] =
    useState(false);

  const [documentId, setDocumentId] =
    useState("demo-anatomie-coeur");

  const [message, setMessage] =
    useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadCourse() {
      try {
        const response = await fetch(
          `/api/education/courses/${courseId}`,
          {
            cache: "no-store",
          },
        );

        const body = await response.json();

        if (!response.ok) {
          throw new Error(
            body.detail ??
              "Cours introuvable.",
          );
        }

        if (!cancelled) {
          setCourse(body);
        }
      } catch (error) {
        if (!cancelled) {
          setMessage(
            error instanceof Error
              ? error.message
              : "Erreur inconnue.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadCourse();

    return () => {
      cancelled = true;
    };
  }, [courseId]);

  async function attachDocument() {
    if (!course) {
      return;
    }

    setMessage("");

    try {
      const response = await fetch(
        `/api/education/courses/${course.course_id}/documents`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            document_id: documentId,
          }),
        },
      );

      const body = await response.json();

      if (!response.ok) {
        throw new Error(
          body.detail ??
            "Impossible d'ajouter la ressource.",
        );
      }

      setCourse(body);
      setShowResourceModal(false);

      setMessage(
        "Ressource pédagogique ajoutée.",
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Erreur inconnue.",
      );
    }
  }

  if (loading) {
    return (
      <main className="course-detail-loading">
        Chargement du cours...
      </main>
    );
  }

  if (!course) {
    return (
      <main className="course-detail-loading">
        {message || "Cours introuvable."}
      </main>
    );
  }

  return (
    <main className="course-detail-page">
      <div className="course-detail-topbar">
        <Link
          href="/courses"
          className="course-back"
        >
          ← Mes cours
        </Link>

        <span className="course-status">
          ● Assistant IA disponible
        </span>
      </div>

      <section className="course-detail-hero">
        <div>
          <div className="edu-tags">
            <span>{course.level}</span>
            <span>{course.subject}</span>
          </div>

          <h1>{course.title}</h1>

          <p>
            Centralisez vos ressources,
            révisez et interrogez
            l&apos;assistant pédagogique.
          </p>
        </div>

        <div className="course-detail-actions">
          <button
            className="edu-secondary"
            onClick={() =>
              setShowResourceModal(true)
            }
          >
            + Ajouter une ressource
          </button>

          <Link
            href="/assistant"
            className="edu-primary-link"
          >
            Réviser avec l&apos;IA
          </Link>
        </div>
      </section>

      {message && (
        <div className="edu-message">
          {message}
        </div>
      )}

      <section className="course-detail-grid">
        <div>
          <div className="course-section-header">
            <div>
              <span className="edu-eyebrow">
                CONTENU DU COURS
              </span>

              <h2>
                Ressources pédagogiques
              </h2>
            </div>

            <span className="course-count">
              {course.document_ids.length}
            </span>
          </div>

          {course.document_ids.length === 0 ? (
            <div className="resource-empty">
              <div className="resource-empty-icon">
                📄
              </div>

              <h3>
                Aucune ressource pour le moment
              </h3>

              <p>
                Ajoutez un support de cours
                pour permettre à RKJO de
                l&apos;exploiter avec l&apos;IA.
              </p>

              <button
                className="edu-primary"
                onClick={() =>
                  setShowResourceModal(true)
                }
              >
                Ajouter une ressource
              </button>
            </div>
          ) : (
            <div className="resource-list">
              {course.document_ids.map(
                (id) => (
                  <article
                    key={id}
                    className="resource-card"
                  >
                    <div className="resource-icon">
                      📄
                    </div>

                    <div>
                      <strong>
                        {id ===
                        "demo-anatomie-coeur"
                          ? "Cours d&apos;anatomie du cœur"
                          : id}
                      </strong>

                      <span>
                        Document indexé dans
                        RKJO RAG
                      </span>
                    </div>

                    <div className="resource-ready">
                      Prêt pour l&apos;IA
                    </div>
                  </article>
                ),
              )}
            </div>
          )}
        </div>

        <aside className="learning-tools">
          <span className="edu-eyebrow">
            OUTILS PÉDAGOGIQUES
          </span>

          <h2>
            Apprendre avec RKJO
          </h2>

          <Link
            href="/assistant"
            className="learning-tool active"
          >
            <span>💬</span>

            <div>
              <strong>
                Poser une question
              </strong>

              <small>
                Réponses basées sur vos
                documents
              </small>
            </div>
          </Link>

          <div className="learning-tool">
            <span>📝</span>

            <div>
              <strong>
                Générer un quiz
              </strong>

              <small>
                Bientôt disponible
              </small>
            </div>
          </div>

          <div className="learning-tool">
            <span>🧠</span>

            <div>
              <strong>
                Flashcards
              </strong>

              <small>
                Bientôt disponible
              </small>
            </div>
          </div>

          <div className="learning-tool">
            <span>📊</span>

            <div>
              <strong>
                Progression
              </strong>

              <small>
                Bientôt disponible
              </small>
            </div>
          </div>
        </aside>
      </section>

      {showResourceModal && (
        <div className="edu-modal-backdrop">
          <div className="edu-modal">
            <div className="edu-modal-header">
              <div>
                <span className="edu-eyebrow">
                  RESSOURCE PÉDAGOGIQUE
                </span>

                <h2>
                  Ajouter une ressource
                </h2>
              </div>

              <button
                className="edu-close"
                onClick={() =>
                  setShowResourceModal(false)
                }
              >
                ×
              </button>
            </div>

            <p className="resource-modal-help">
              Pour ce MVP, sélectionnez un
              document déjà indexé dans RKJO.
              L&apos;import direct depuis cette
              fenêtre viendra ensuite.
            </p>

            <label>
              Document disponible
              <select
                value={documentId}
                onChange={(event) =>
                  setDocumentId(
                    event.target.value,
                  )
                }
                className="resource-select"
              >
                <option value="demo-anatomie-coeur">
                  Cours d&apos;anatomie du cœur
                </option>
              </select>
            </label>

            <div className="edu-modal-actions">
              <button
                className="edu-secondary"
                onClick={() =>
                  setShowResourceModal(false)
                }
              >
                Annuler
              </button>

              <button
                className="edu-primary"
                onClick={attachDocument}
              >
                Ajouter au cours
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
