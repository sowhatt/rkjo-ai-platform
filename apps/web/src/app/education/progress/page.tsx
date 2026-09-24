import EducationShell from "@/components/education/EducationShell";

export default function EducationProgressPage() {
  return (
    <EducationShell active="progress">
      <header className="rkjo-demo-header">
        <div>
          <span className="rkjo-edu-kicker">
            TON APPRENTISSAGE
          </span>
          <h1>Ma progression</h1>
          <p>
            RKJO distingue ce que tu réussis de ce que tu
            maîtrises réellement en autonomie.
          </p>
        </div>
      </header>

      <section className="rkjo-progress-summary">
        <article>
          <span>Progression</span>
          <strong>64%</strong>
          <small>Parcours actuel</small>
        </article>

        <article>
          <span>Autonomie</span>
          <strong>78%</strong>
          <small>Réussites sans aide</small>
        </article>

        <article>
          <span>Compétences maîtrisées</span>
          <strong>8</strong>
          <small>Vérifiées par RKJO</small>
        </article>
      </section>

      <section className="rkjo-mastery-panel">
        <div className="rkjo-mastery-heading">
          <div>
            <span className="rkjo-edu-kicker">
              COMPÉTENCES
            </span>
            <h2>Ce que tu maîtrises vraiment</h2>
          </div>
        </div>

        <article className="rkjo-mastery-row">
          <span className="rkjo-skill-icon success">✓</span>
          <div>
            <strong>Dérivées</strong>
            <small>
              Vérifiée en autonomie · Maîtrisée
            </small>
          </div>
          <b>82%</b>
        </article>

        <article className="rkjo-mastery-row">
          <span className="rkjo-skill-icon warning">↗</span>
          <div>
            <strong>Limites</strong>
            <small>
              Réussite avec aide · À vérifier sans aide
            </small>
          </div>
          <b>54%</b>
        </article>

        <article className="rkjo-mastery-row">
          <span className="rkjo-skill-icon">○</span>
          <div>
            <strong>Continuité</strong>
            <small>Apprentissage à poursuivre</small>
          </div>
          <b>38%</b>
        </article>
      </section>

      <div className="rkjo-proof-value">
        <span>✓</span>
        <div>
          <strong>Proof of Learning</strong>
          <p>
            Une compétence n&apos;est déclarée maîtrisée que
            lorsque RKJO dispose de preuves suffisantes de
            réussite autonome.
          </p>
        </div>
      </div>
    </EducationShell>
  );
}
