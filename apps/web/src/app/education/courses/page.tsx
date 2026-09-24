import Link from "next/link";
import EducationShell from "@/components/education/EducationShell";

export default function EducationCoursesPage() {
  return (
    <EducationShell active="courses">
      <header className="rkjo-demo-header">
        <div>
          <span className="rkjo-edu-kicker">
            ESPACE PÉDAGOGIQUE
          </span>
          <h1>Mes cours</h1>
          <p>
            Retrouve tes apprentissages et reprends là où
            tu t&apos;es arrêté.
          </p>
        </div>
      </header>

      <section className="rkjo-demo-grid">
        <article className="rkjo-demo-course featured">
          <span className="rkjo-demo-tag">
            MATHÉMATIQUES
          </span>
          <h2>Mathématiques</h2>
          <p>
            Exercices progressifs, accompagnement RKJO et
            vérification de ton autonomie.
          </p>

          <div className="rkjo-demo-progress-row">
            <span>Progression</span>
            <strong>64%</strong>
          </div>

          <div className="rkjo-progress">
            <i style={{ width: "64%" }} />
          </div>

          <Link
            className="rkjo-action-primary"
            href="/education/session"
          >
            Continuer mon apprentissage →
          </Link>
        </article>

        <article className="rkjo-demo-course">
          <span className="rkjo-demo-tag">
            PROCHAINEMENT
          </span>
          <h2>Nouveaux parcours</h2>
          <p>
            Les autres matières apparaîtront ici selon ton
            programme et ton niveau.
          </p>
        </article>
      </section>
    </EducationShell>
  );
}
