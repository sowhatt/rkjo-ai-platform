"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
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
type Assessment = {
  id: string;
  title: string;
  questions: { id: string; prompt: string; competency_code: string | null }[];
};

export default function EducationCourseDetailPage() {
  const params = useParams<{ courseId: string }>();
  const courseId = params.courseId;
  const [course, setCourse] = useState<Course | null>(null);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [exerciseError, setExerciseError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setLoading(true);
      setError("");
      setExerciseError("");
      try {
        const id = encodeURIComponent(courseId);
        const courseResponse = await fetch(`/api/education/courses/${id}`, {
          cache: "no-store", signal: controller.signal,
        });
        if (!courseResponse.ok) throw new Error("Ce cours est introuvable ou inaccessible.");
        const nextCourse = (await courseResponse.json()) as Course;
        if (!controller.signal.aborted) setCourse(nextCourse);

        const assessmentResponse = await fetch(`/api/education/courses/${id}/assessments`, {
          cache: "no-store", signal: controller.signal,
        });
        if (!assessmentResponse.ok) {
          if (!controller.signal.aborted) setExerciseError("Les exercices ne peuvent pas être chargés actuellement.");
        } else {
          const items: unknown = await assessmentResponse.json();
          if (!Array.isArray(items)) throw new Error("Format des exercices inattendu.");
          if (!controller.signal.aborted) setAssessments(items as Assessment[]);
        }
      } catch (cause) {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Erreur de chargement.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [courseId]);

  return (
    <EducationShell active="courses">
      <Link href="/education/courses" className="text-sm font-semibold text-blue-700">← Mes cours</Link>
      {loading ? <p role="status" className="mt-8">Chargement du cours…</p> : error ? (
        <section role="alert" className="mt-8 rounded-xl border border-amber-200 bg-amber-50 p-5">{error}</section>
      ) : course ? (
        <>
          <header className="mt-7 rounded-2xl bg-blue-950 p-7 text-white">
            <span className="text-xs font-semibold uppercase tracking-wider text-blue-200">{course.subject} · {course.level}</span>
            <h1 className="mt-3 text-3xl font-bold">{course.title}</h1>
            <p className="mt-3 text-blue-100">
              Voici les ressources et les activités réellement associées à ce cours.
              Choisis une activité pour préparer ta prochaine séance.
            </p>
          </header>
          <section className="mt-7 rounded-2xl border border-slate-200 bg-white p-6">
            <h2 className="text-xl font-bold">Supports pédagogiques</h2>
            {course.document_ids.length ? (
              <p className="mt-2 text-slate-600">
                {course.document_ids.length} document{course.document_ids.length !== 1 ? "s" : ""} référencé{course.document_ids.length !== 1 ? "s" : ""} pour ce cours.
              </p>
            ) : (
              <p className="mt-2 text-slate-600">Aucun support n'est encore associé à ce cours.</p>
            )}
            <Link href="/education/resources" className="mt-4 inline-block font-semibold text-blue-700">
              Consulter les ressources →
            </Link>
          </section>
          <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6">
            <h2 className="text-xl font-bold">Exercices disponibles</h2>
            {exerciseError && <p role="alert" className="mt-2 text-amber-800">{exerciseError}</p>}
            {!exerciseError && assessments.length === 0 && (
              <p className="mt-2 text-slate-600">Aucune évaluation n'a encore été préparée pour ce cours.</p>
            )}
            <div className="mt-4 grid gap-3">
              {assessments.map((assessment) => (
                <article key={assessment.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <h3 className="font-semibold">{assessment.title}</h3>
                  <p className="mt-1 text-sm text-slate-600">{assessment.questions.length} question{assessment.questions.length !== 1 ? "s" : ""}</p>
                  {assessment.questions.length > 0 && (
                    <p className="mt-2 text-sm text-slate-600">
                      Exemple de question : {assessment.questions[0].prompt}
                    </p>
                  )}
                </article>
              ))}
            </div>
            <p className="mt-4 text-sm text-slate-600">
              Pour répondre et faire valider les acquis, une session individuelle étudiante est nécessaire.
              La séance d'évaluation reste protégée tant que cette connexion n'est pas disponible.
            </p>
          </section>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/education/tutor" className="rounded-xl bg-blue-900 px-5 py-3 font-semibold text-white">
              Comprendre avec le professeur IA →
            </Link>
            <Link href="/education/study-tools" className="rounded-xl border border-slate-200 bg-white px-5 py-3 font-semibold">
              Outils de révision →
            </Link>
          </div>
        </>
      ) : null}
    </EducationShell>
  );
}
