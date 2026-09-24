import Link from "next/link";
import EducationShell from "@/components/education/EducationShell";

export default function EducationTutorPage() {
  return (
    <EducationShell active="tutor">
      <header className="rkjo-demo-header">
        <div>
          <span className="rkjo-edu-kicker">
            PROFESSEUR RKJO
          </span>
          <h1>Comprendre, pas copier.</h1>
          <p>
            Ton professeur IA adapte son aide pour te faire
            progresser sans faire le travail à ta place.
          </p>
        </div>
      </header>

      <section className="rkjo-professor-hero">
        <div className="rkjo-professor-orb">✦</div>

        <div>
          <span className="rkjo-demo-tag">
            ACCOMPAGNEMENT ADAPTATIF
          </span>
          <h2>Je suis là pour te guider.</h2>
          <p>
            Je peux poser une question, donner un indice,
            expliquer une méthode ou t&apos;aider à identifier
            ton erreur. Le niveau d&apos;aide utilisé est pris
            en compte dans ton autonomie.
          </p>

          <div className="rkjo-help-levels">
            <span>Question socratique</span>
            <span>Indice</span>
            <span>Méthode guidée</span>
          </div>

          <Link
            href="/education/session"
            className="rkjo-action-primary"
          >
            Commencer avec mon professeur →
          </Link>
        </div>
      </section>

      <section className="rkjo-demo-info-grid">
        <article>
          <strong>✦ Aide progressive</strong>
          <p>
            RKJO commence par l&apos;aide la plus légère avant
            d&apos;expliquer davantage.
          </p>
        </article>

        <article>
          <strong>◎ Autonomie mesurée</strong>
          <p>
            Une bonne réponse avec beaucoup d&apos;aide
            n&apos;est pas confondue avec une réussite autonome.
          </p>
        </article>

        <article>
          <strong>✓ Apprentissage vérifié</strong>
          <p>
            Après une aide importante, RKJO peut vérifier la
            compétence avec un nouvel exercice sans aide.
          </p>
        </article>
      </section>
    </EducationShell>
  );
}
