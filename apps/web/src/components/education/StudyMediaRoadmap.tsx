export default function StudyMediaRoadmap() {
  return (
    <section className="mt-6 grid gap-4 md:grid-cols-2" aria-label="Autres formats de cours">
      <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <span className="text-3xl" aria-hidden="true">🎙️</span>
          <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800">En préparation</span>
        </div>
        <h2 className="mt-4 text-xl font-bold text-slate-900">Cours magistral enregistré</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Importer un enregistrement audio autorisé, le transcrire, le découper par thème
          et retrouver les passages avec leur horodatage.
        </p>
        <p className="mt-3 text-sm font-semibold text-slate-700">MP3, M4A, WAV, WebM, OGG · 50 Mo maximum visés</p>
        <p className="mt-2 text-xs text-slate-500">
          Respect du droit à l&apos;enregistrement et de la confidentialité des personnes.
          La transcription n&apos;est pas encore active.
        </p>
      </article>
      <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <span className="text-3xl" aria-hidden="true">📚</span>
          <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800">En préparation</span>
        </div>
        <h2 className="mt-4 text-xl font-bold text-slate-900">Apprendre à partir d&apos;un livre</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Importer un livre PDF ou EPUB autorisé, choisir les chapitres utiles et
          créer des supports de révision citant les pages d&apos;origine.
        </p>
        <p className="mt-3 text-sm font-semibold text-slate-700">PDF ou EPUB · 50 Mo maximum visés</p>
        <p className="mt-2 text-sm text-blue-800">
          Livre en anglais ? Une traduction de travail en français pourra être demandée,
          avec accès au texte original.
        </p>
        <p className="mt-2 text-xs text-slate-500">
          Traduction et import de livres non encore actifs. Utiliser seulement des ouvrages
          dont le traitement et la traduction sont autorisés.
        </p>
      </article>
    </section>
  );
}
