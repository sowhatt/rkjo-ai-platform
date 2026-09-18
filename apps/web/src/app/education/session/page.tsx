import { Suspense } from "react";

import EducationSession from "@/components/education/EducationSession";

function SessionLoading() {
  return (
    <main className="rkjo-session-page">
      <div className="rkjo-session-shell">
        <section className="rkjo-session-empty">
          <span>✦ RKJO Education</span>
          <h1>Préparation de ta session…</h1>
          <p>RKJO charge ton parcours personnalisé.</p>
        </section>
      </div>
    </main>
  );
}

export default function EducationSessionPage() {
  return (
    <Suspense fallback={<SessionLoading />}>
      <EducationSession />
    </Suspense>
  );
}
