import Link from "next/link";
import StudyPdfPreview from "@/components/education/StudyPdfPreview";

const tools = [
  {id:"fiches",icon:"📑",title:"Fiches de révision",description:"Résumés et notes de cours avec définitions, tableaux et notions à mémoriser.",example:"À partir d’un CM : notions clés, définitions et références aux pages du support."},
  {id:"cartes",icon:"🧠",title:"Cartes mentales",description:"Visualisation des notions, mécanismes et prérequis reliés au cours.",example:"Anatomie → structure → fonction → mécanismes physiologiques."},
  {id:"flashcards",icon:"🗂️",title:"Flashcards intelligentes",description:"Questions-réponses révisées à intervalles adaptés aux difficultés.",example:"Question : quelle est la fonction de cette structure ? Réponse expliquée."},
  {id:"qcm",icon:"✅",title:"QCM et exercices",description:"Entraînement progressif sur les CM et exercices de TD.",example:"QCM par UE, corrigés expliqués et exercices à refaire."},
  {id:"examens",icon:"🎓",title:"Examens blancs",description:"Simulation de partiels, contrôle du temps et évaluation sans aide.",example:"Examen blanc organisé par UE et selon le programme de l’étudiant."},
] as const;

export default function EducationStudyToolsPage() {
  return (
    <main className="min-h-screen bg-slate-50 px-5 py-10 text-slate-900 sm:px-10">
      <div className="mx-auto max-w-5xl">
        <Link href="/education" className="text-sm font-semibold text-blue-700 hover:underline">← Retour à l’accueil</Link>
        <p className="mt-8 text-xs font-bold uppercase tracking-widest text-blue-700">RKJO Education · Santé</p>
        <h1 className="mt-2 text-3xl font-bold sm:text-4xl">Mes outils de révision</h1>
        <p className="mt-4 max-w-3xl text-slate-600">
          Médecine, pharmacie ou soins infirmiers : tes cours magistraux, TD et TP
          sont la base de ton apprentissage. Ce catalogue présente les outils en préparation.
        </p>
        <div className="mt-6 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900" role="status">
          Démonstration d’interface : les exemples ci-dessous ne proviennent pas encore de tes documents.
          La génération IA, les exports et l’évaluation seront activés après leur intégration et leurs tests.
        </div>
        <StudyPdfPreview />
        <div className="mt-8 grid gap-5 sm:grid-cols-2">
          {tools.map((tool) => (
            <section id={tool.id} key={tool.id} className="scroll-mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100 text-4xl" aria-hidden="true">{tool.icon}</div>
              <h2 className="text-xl font-bold">{tool.title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">{tool.description}</p>
              <div className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-700">
                <strong>Exemple pédagogique</strong>
                <p className="mt-1">{tool.example}</p>
              </div>
              <p className="mt-3 text-xs font-medium text-amber-800">Génération automatique : en préparation</p>
            </section>
          ))}
        </div>
        <div className="mt-8 rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="text-lg font-bold">Commencer par tes supports</h2>
          <p className="mt-2 text-sm text-slate-600">
            Retrouve l’espace de ressources RKJO pour préparer tes documents de cours.
          </p>
          <Link className="mt-4 inline-block rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-700" href="/education/resources">
            Ouvrir mes ressources →
          </Link>
        </div>
      </div>
    </main>
  );
}
