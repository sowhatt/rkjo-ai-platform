"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import EducationShell from "@/components/education/EducationShell";

type Course = {
  course_id: string;
  title: string;
  subject: string;
  level: string;
  curriculum_id: string | null;
  document_ids: string[];
};

export default function EducationCoursesPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    async function loadCourses() {
      try {
        const response = await fetch("/api/education/courses", {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error("Les cours ne sont pas accessibles pour le moment.");
        }
        const data: unknown = await response.json();
        if (!Array.isArray(data)) throw new Error("Format de cours inattendu.");
        if (!controller.signal.aborted) setCourses(data as Course[]);
      } catch (cause) {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "Erreur de chargement.");
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void loadCourses();
    return () => controller.abort();
  }, []);

  return (
    <EducationShell active="courses">
      <header className="rkjo-demo-header">
        <div>
          <span className="rkjo-edu-kicker">PARCOURS PÉDAGOGIQUE</span>
          <h1>Mes cours</h1>
          <p>Choisis une matière, explore ses ressources et découvre les exercices disponibles.</p>
        </div>
      </header>
      {loading ? (
        <p role="status" className="mt-8 text-slate-600">Chargement des cours…</p>
      ) : error ? (
        <section role="alert" className="mt-8 rounded-xl border border-amber-200 bg-amber-50 p-5">
          <h2 className="font-semibold">Impossible d'afficher tes cours</h2>
          <p className="mt-2">{error}</p>
          <p className="mt-2 text-sm">Vérifie la connexion avec le service Education.</p>
        </section>
      ) : courses.length === 0 ? (
        <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-7">
          <h2 className="text-xl font-bold">Aucun cours disponible</h2>
          <p className="mt-2 text-slate-600">
            Ton établissement ou ton professeur doit encore ajouter un cours au catalogue.
            Aucune progression n'est inventée.
          </p>
          <Link href="/education/resources" className="mt-5 inline-block font-semibold text-blue-700">
            Explorer les ressources →
          </Link>
        </section>
      ) : (
        <section className="mt-7 grid gap-5 md:grid-cols-2" aria-label="Cours disponibles">
          {courses.map((course) => (
            <article key={course.course_id} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <span className="rkjo-edu-kicker">{course.subject || "MATIÈRE"}</span>
              <h2 className="mt-2 text-xl font-bold text-slate-900">{course.title}</h2>
              <p className="mt-2 text-sm text-slate-600">Niveau : {course.level || "Non renseigné"}</p>
              <p className="mt-2 text-sm text-slate-600">
                {course.document_ids.length} support{course.document_ids.length !== 1 ? "s" : ""} associé{course.document_ids.length !== 1 ? "s" : ""}
              </p>
              <Link
                href={`/education/courses/${encodeURIComponent(course.course_id)}`}
                className="mt-5 inline-block rounded-xl bg-blue-900 px-4 py-3 font-semibold text-white hover:bg-blue-800"
              >
                Ouvrir ce cours →
              </Link>
            </article>
          ))}
        </section>
      )}
    </EducationShell>
  );
}
