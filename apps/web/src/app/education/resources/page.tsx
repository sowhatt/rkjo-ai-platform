import EducationShell from "@/components/education/EducationShell";

export default function EducationResourcesPage() {
  return (
    <EducationShell active="resources">
      <header className="rkjo-demo-header">
        <div>
          <span className="rkjo-edu-kicker">
            TES RESSOURCES
          </span>
          <h1>Ressources pédagogiques</h1>
          <p>
            Les supports utiles à ton apprentissage,
            sélectionnés pour ton cours et ton niveau.
          </p>
        </div>
      </header>

      <section className="rkjo-resource-grid">
        <article>
          <span className="rkjo-resource-icon">▤</span>
          <div>
            <small>FICHE DE COURS</small>
            <h2>Notions essentielles</h2>
            <p>
              Les points à connaître avant de commencer les
              exercices.
            </p>
          </div>
        </article>

        <article>
          <span className="rkjo-resource-icon">✦</span>
          <div>
            <small>MÉTHODE</small>
            <h2>Comprendre étape par étape</h2>
            <p>
              Une méthode guidée pour raisonner sans obtenir
              directement la réponse.
            </p>
          </div>
        </article>

        <article>
          <span className="rkjo-resource-icon">✓</span>
          <div>
            <small>ENTRAÎNEMENT</small>
            <h2>Exercices progressifs</h2>
            <p>
              Des exercices adaptés pour consolider chaque
              compétence.
            </p>
          </div>
        </article>
      </section>

      <div className="rkjo-demo-note">
        Les documents techniques et l&apos;indexation RAG
        restent réservés au back-office RKJO.
      </div>
    </EducationShell>
  );
}
