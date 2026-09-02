"use client";

import {
  FormEvent,
  useEffect,
  useState,
} from "react";

type Course = {
  course_id: string;
  title: string;
  subject: string;
  level: string;
  curriculum_id: string | null;
  document_ids: string[];
};

const navItems = [
  "Tableau de bord",
  "Mes cours",
  "Documents",
  "Assistant IA",
  "Programmes",
];

export default function CoursesPage() {
  const [courses, setCourses] =
    useState<Course[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [showCreate, setShowCreate] =
    useState(false);

  const [message, setMessage] =
    useState("");

  const [title, setTitle] =
    useState("");

  const [subject, setSubject] =
    useState("");

  const [level, setLevel] =
    useState("");

  async function loadCourses() {
    setLoading(true);
    setMessage("");

    try {
      const response = await fetch(
        "/api/education/courses",
        {
          cache: "no-store",
        },
      );

      const body = await response.json();

      if (!response.ok) {
        throw new Error(
          body.detail ??
            "Impossible de charger les cours.",
        );
      }

      setCourses(body);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Erreur inconnue.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCourses();
  }, []);

  async function createCourse(
    event: FormEvent,
  ) {
    event.preventDefault();

    setMessage("");

    const generatedId = title
      .toLowerCase()
      .normalize("NFD")
      .replace(
        /[\u0300-\u036f]/g,
        "",
      )
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");

    const response = await fetch(
      "/api/education/courses",
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json",
        },
        body: JSON.stringify({
          course_id: generatedId,
          title,
          subject,
          level,
        }),
      },
    );

    const body =
      await response.json();

    if (!response.ok) {
      setMessage(
        body.detail ??
          "Impossible de créer le cours.",
      );
      return;
    }

    setCourses((current) => [
      body,
      ...current.filter(
        (item) =>
          item.course_id !== body.course_id,
      ),
    ]);

    setShowCreate(false);

    setMessage(
      "Cours créé avec succès.",
    );
  }

  return (
    <div className="edu-shell">
      <aside className="edu-sidebar">
        <div className="edu-brand">
          <div className="edu-logo">
            R
          </div>

          <div>
            <strong>RKJO</strong>
            <span>Education</span>
          </div>
        </div>

        <nav>
          {navItems.map((item) => (
            <button
              key={item}
              className={
                item === "Mes cours"
                  ? "edu-nav active"
                  : "edu-nav"
              }
            >
              {item}
            </button>
          ))}
        </nav>

        <div className="edu-sidebar-footer">
          <div className="edu-avatar">
            RK
          </div>

          <div>
            <strong>Compte pilote</strong>
            <span>Environnement démo</span>
          </div>
        </div>
      </aside>

      <main className="edu-main">
        <header className="edu-header">
          <div>
            <span className="edu-eyebrow">
              ESPACE PÉDAGOGIQUE
            </span>

            <h1>Mes cours</h1>

            <p>
              Centralisez vos cours,
              ressources et assistants IA.
            </p>
          </div>

          <button
            className="edu-primary"
            onClick={() =>
              setShowCreate(true)
            }
          >
            + Nouveau cours
          </button>
        </header>

        <section className="edu-stats">
          <article>
            <span>Cours actifs</span>
            <strong>
              {courses.length}
            </strong>
          </article>

          <article>
            <span>
              Documents pédagogiques
            </span>
            <strong>
              {
                courses.reduce(
                  (total, item) =>
                    total
                    + item.document_ids.length,
                  0,
                )
              }
            </strong>
          </article>

          <article>
            <span>Assistant IA</span>
            <strong>Actif</strong>
          </article>
        </section>

        {message && (
          <div className="edu-message">
            {message}
          </div>
        )}

        <section className="edu-section">
          <div className="edu-section-title">
            <div>
              <h2>Vos cours</h2>
              <p>
                Continuez là où vous vous
                êtes arrêté.
              </p>
            </div>
          </div>

          {loading ? (
            <div className="edu-empty">
              Chargement...
            </div>
          ) : courses.length > 0 ? (
            <div className="edu-course-list">
              {courses.map((course) => (
                <article
                  key={course.course_id}
                  className="edu-course-card"
                >
                  <div className="edu-course-icon">
                    📚
                  </div>

                  <div className="edu-course-content">
                    <div className="edu-tags">
                      <span>
                        {course.level}
                      </span>

                      <span>
                        {course.subject}
                      </span>
                    </div>

                    <h3>
                      {course.title}
                    </h3>

                    <p>
                      Retrouvez les ressources
                      pédagogiques du cours et
                      révisez avec RKJO.
                    </p>

                    <div className="edu-course-meta">
                      <span>
                        📄{" "}
                        {
                          course.document_ids
                            .length
                        }{" "}
                        ressource
                        {course.document_ids
                          .length !== 1
                          ? "s"
                          : ""}
                      </span>

                      <span>
                        ✨ Assistant IA prêt
                      </span>
                    </div>
                  </div>

                  <div className="edu-course-actions">
                    <a
                      href={`/courses/${course.course_id}`}
                      className="edu-primary-link"
                    >
                      Ouvrir le cours →
                    </a>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="edu-empty">
              <h3>
                Créez votre premier cours
              </h3>

              <p>
                Ajoutez un cours et commencez
                à exploiter RKJO Education.
              </p>

              <button
                className="edu-primary"
                onClick={() =>
                  setShowCreate(true)
                }
              >
                Créer un cours
              </button>
            </div>
          )}
        </section>

        {showCreate && (
          <div className="edu-modal-backdrop">
            <form
              className="edu-modal"
              onSubmit={createCourse}
            >
              <div className="edu-modal-header">
                <div>
                  <span className="edu-eyebrow">
                    NOUVEAU COURS
                  </span>

                  <h2>
                    Créer un cours
                  </h2>
                </div>

                <button
                  type="button"
                  className="edu-close"
                  onClick={() =>
                    setShowCreate(false)
                  }
                >
                  ×
                </button>
              </div>

              <label>
                Nom du cours
                <input
                  value={title}
                  onChange={(e) =>
                    setTitle(
                      e.target.value,
                    )
                  }
                  placeholder="Ex. Anatomie du cœur"
                  required
                />
              </label>

              <label>
                Matière
                <input
                  value={subject}
                  onChange={(e) =>
                    setSubject(
                      e.target.value,
                    )
                  }
                  placeholder="Ex. Anatomie"
                  required
                />
              </label>

              <label>
                Niveau
                <input
                  value={level}
                  onChange={(e) =>
                    setLevel(
                      e.target.value,
                    )
                  }
                  placeholder="Ex. Médecine"
                  required
                />
              </label>

              <div className="edu-modal-actions">
                <button
                  type="button"
                  className="edu-secondary"
                  onClick={() =>
                    setShowCreate(false)
                  }
                >
                  Annuler
                </button>

                <button
                  type="submit"
                  className="edu-primary"
                >
                  Créer le cours
                </button>
              </div>
            </form>
          </div>
        )}
      </main>
    </div>
  );
}
