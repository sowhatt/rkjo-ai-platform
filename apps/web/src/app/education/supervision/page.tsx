"use client";

import { useEffect, useMemo, useState } from "react";
import EducationShell from "@/components/education/EducationShell";

type SupervisionAlert = {
  code: "low_autonomy" | "proof_failed" | "assistance_repeated";
  severity: "warning" | "critical";
  message: string;
};

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

type LearnerDetail = LearnerState & { alerts: SupervisionAlert[] };

function alertLabel(code: SupervisionAlert["code"]) {
  if (code === "low_autonomy") return "Autonomie faible";
  if (code === "proof_failed") return "Preuve échouée";
  return "Assistance répétée";
}

export default function SupervisionPage() {
  const [learners, setLearners] = useState<LearnerState[]>([]);
  const [connected, setConnected] = useState(false);
  const [message, setMessage] = useState("");
  const [selected, setSelected] = useState<LearnerDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  async function openLearner(learnerId: string) {
    setDetailLoading(true);
    try {
      const response = await fetch(`/api/education/supervision/learners/${learnerId}/detail`, { cache: "no-store" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Détail élève indisponible.");
      setSelected(body);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Erreur inconnue.");
    } finally {
      setDetailLoading(false);
    }
  }

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
      const next = JSON.parse((event as MessageEvent).data) as LearnerState[];
      setLearners(next);
      setConnected(true);
      setMessage("");
      if (selected) void openLearner(selected.learner_id);
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
  }, [selected?.learner_id]);

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
              <thead><tr><th>Élève</th><th>État</th><th>Réponses</th><th>Indices</th><th>Tuteur</th><th>Autonomie</th><th>Maîtrise</th><th>Preuve</th><th></th></tr></thead>
              <tbody>{learners.map((learner) => (
                <tr key={learner.learner_id}>
                  <td><strong>{learner.learner_id.slice(0, 8)}</strong><small>{learner.course_id ? `Cours ${learner.course_id.slice(0, 8)}` : "Cours non renseigné"}</small></td>
                  <td><span className={learner.active ? "supervision-status active" : "supervision-status"}>{learner.active ? "En activité" : "Terminé"}</span></td>
                  <td>{learner.answers_submitted}</td><td>{learner.hints_requested}</td><td>{learner.tutor_requests}</td>
                  <td>{learner.autonomy_score ?? "—"}{learner.autonomy_score !== null ? "%" : ""}</td>
                  <td>{learner.mastery ?? "—"}</td>
                  <td>{learner.proof_status ?? "—"}</td>
                  <td><button className="supervision-detail-button" onClick={() => void openLearner(learner.learner_id)}>Voir le détail</button></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </section>

      {(selected || detailLoading) && (
        <section className="supervision-detail" aria-live="polite">
          {detailLoading && !selected ? (
            <div className="edu-empty"><h3>Chargement du détail…</h3></div>
          ) : selected ? (
            <>
              <div className="course-section-header">
                <div><span className="rkjo-edu-kicker">DÉTAIL ÉLÈVE</span><h2>Situation pédagogique</h2></div>
                <button className="supervision-detail-close" onClick={() => setSelected(null)}>Fermer</button>
              </div>
              <div className="supervision-detail-grid">
                <article><span>Autonomie</span><strong>{selected.autonomy_score ?? "—"}{selected.autonomy_score !== null ? "%" : ""}</strong></article>
                <article><span>Maîtrise</span><strong>{selected.mastery ?? "—"}</strong></article>
                <article><span>Preuve</span><strong>{selected.proof_status ?? "—"}</strong></article>
                <article><span>Activité</span><strong>{selected.active ? "En cours" : "Terminée"}</strong></article>
              </div>
              <div className="supervision-detail-context">
                <p><strong>Élève</strong><span>{selected.learner_id}</span></p>
                <p><strong>Cours</strong><span>{selected.course_id ?? "Non renseigné"}</span></p>
                <p><strong>Évaluation</strong><span>{selected.assessment_id ?? "Non renseignée"}</span></p>
                <p><strong>Réponses</strong><span>{selected.answers_submitted}</span></p>
              </div>
              <div className="supervision-alerts">
                <h3>Alertes pédagogiques</h3>
                {selected.alerts.length === 0 ? (
                  <div className="supervision-alert-ok">Aucune alerte pédagogique actuellement.</div>
                ) : selected.alerts.map((alert) => (
                  <div key={alert.code} className={alert.severity === "critical" ? "supervision-alert critical" : "supervision-alert"}>
                    <strong>{alertLabel(alert.code)}</strong>
                    <span>{alert.message}</span>
                  </div>
                ))}
              </div>
            </>
          ) : null}
        </section>
      )}
    </EducationShell>
  );
}
