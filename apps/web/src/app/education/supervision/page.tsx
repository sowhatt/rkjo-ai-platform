"use client";

import { useEffect, useMemo, useState } from "react";
import EducationShell from "@/components/education/EducationShell";

type LearnerState = {
  tenant_id: string;
  learner_id: string;
  course_id: string | null;
  session_id: string | null;
  assessment_id: string | null;
  active: boolean;
  answers_submitted: number;
  hints_requested: number;
  tutor_requests: number;
  autonomy_score: number | null;
  mastery: string | null;
  proof_status: string | null;
  last_event_at: string | null;
};

export default function SupervisionPage() {
  const [learners, setLearners] = useState<LearnerState[]>([]);
  const [connected, setConnected] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetch("/api/education/supervision/snapshot", { cache: "no-store" })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail ?? "Supervision indisponible.");
        if (!cancelled) setLearners(body);
      })
      .catch((error) => !cancelled && setMessage(error instanceof Error ? error.message : "Erreur inconnue."));

    const stream = new EventSource("/api/education/supervision/stream");
    stream.addEventListener("supervision.snapshot", (event) => {
      if (cancelled) return;
      setLearners(JSON.parse((event as MessageEvent).data));
      setConnected(true);
      setMessage("");
    });
    stream.onerror = () => {
      if (!cancelled) {
        setConnected(false);
        setMessage("Reconnexion au flux temps réel…");
      }
    };
    return () => {
      cancelled = true;
      stream.close();
    };
  }, []);

  const stats = useMemo(() => ({
    active: learners.filter((item) => item.active).length,
    assistance: learners.filter((item) => item.hints_requested > 0 || item.tutor_requests > 0).length,
    proof: learners.filter((item) => item.proof_status === "failed").length,
  }), [learners]);

  return (
    <EducationShell active="supervision">
      <header className="rkjo-edu-topbar">
        <div>
          <span className="rkjo-edu-kicker">ESPACE PROFESSEUR</span>
          <h1>Supervision en direct</h1>
          <p>Suivez l’activité, l’autonomie, la maîtrise et les preuves d’apprentissage.</p>
        </div>
        <span className={connected ? "supervision-live online" : "supervision-live"}>
          {connected ? "● Temps réel connecté" : "○ Connexion…"}
        </span>
      </header>

      <section className="rkjo-edu-summary" aria-label="Indicateurs de supervision">
        <article><span>Élèves actifs</span><strong>{stats.active}</strong><small>Sessions en cours</small></article>
        <article><span>Avec assistance</span><strong>{stats.assistance}</strong><small>Indice ou professeur IA utilisé</small></article>
        <article><span>Preuves à revoir</span><strong>{stats.proof}</strong><small>Validation d’apprentissage nécessaire</small></article>
      </section>

      {message && <div className="edu-message">{message}</div>}

      <section className="supervision-panel">
        <div className="course-section-header">
          <div><span className="rkjo-edu-kicker">CLASSE EN DIRECT</span><h2>État pédagogique actuel</h2></div>
          <span>{learners.length} élève{learners.length !== 1 ? "s" : ""}</span>
        </div>
        {learners.length === 0 ? (
          <div className="edu-empty"><h3>Aucune session active</h3><p>Les élèves apparaîtront ici dès qu’un événement pédagogique sera reçu.</p></div>
        ) : (
          <div className="supervision-table-wrap">
            <table className="supervision-table">
              <thead><tr><th>Élève</th><th>État</th><th>Réponses</th><th>Indices</th><th>Tuteur</th><th>Autonomie</th><th>Maîtrise</th><th>Preuve</th></tr></thead>
              <tbody>{learners.map((learner) => (
                <tr key={learner.learner_id}>
                  <td><strong>{learner.learner_id.slice(0, 8)}</strong><small>{learner.course_id ? `Cours ${learner.course_id.slice(0, 8)}` : "Cours non renseigné"}</small></td>
                  <td><span className={learner.active ? "supervision-status active" : "supervision-status"}>{learner.active ? "En activité" : "Terminé"}</span></td>
                  <td>{learner.answers_submitted}</td><td>{learner.hints_requested}</td><td>{learner.tutor_requests}</td>
                  <td>{learner.autonomy_score ?? "—"}{learner.autonomy_score !== null ? "%" : ""}</td>
                  <td>{learner.mastery ?? "—"}</td>
                  <td>{learner.proof_status ?? "—"}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </section>
    </EducationShell>
  );
}
