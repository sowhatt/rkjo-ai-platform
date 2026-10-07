"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import EducationShell from "@/components/education/EducationShell";

type TodayRecommendation = {
  action: string; target_competency: string | null; rule_id: string;
  explanation: string; policy_version: string;
  mastery: number | null; autonomy: number | null; retention: number | null; challenge_id?: string | null; source?: string;
};
const actionLabels: Record<string,string> = {
  positioning_test:"Faire mon positionnement", remediate:"Reprendre cette notion",
  practice_similar:"Faire un exercice similaire", practice_prerequisite:"Revoir le prérequis",
  reexplain_differently:"Réexpliquer autrement", review:"Réviser maintenant",
  request_proof:"Passer une Proof", increase_difficulty:"Augmenter la difficulté",
  practice_timed:"M’entraîner en temps limité", advance:"Continuer",
  start_mock_exam:"Démarrer l’examen blanc", mark_for_review:"Marquer pour revue"
};

export default function EducationToday(){
  const params=useSearchParams(); const learnerId=params.get("learnerId") ?? ""; const courseId=params.get("courseId") ?? "";
  const [data,setData]=useState<TodayRecommendation|null>(null);
  const [error,setError]=useState("");
  useEffect(()=>{if(!learnerId)return; void fetch(`/api/education/learners/${learnerId}/today`,{cache:"no-store"})
    .then(async r=>{const p=await r.json(); if(!r.ok)throw new Error(p.detail??"Recommandation indisponible"); return p;})
    .then(setData).catch(e=>setError(e instanceof Error?e.message:"Recommandation indisponible"));},[learnerId]);
  const pct=(v:number|null)=>v===null?"—":`${Math.round(v*100)}%`;
  return <EducationShell active="today">
    <header className="rkjo-supports-header"><div><span className="rkjo-edu-kicker">AUJOURD’HUI</span><h1>Ta prochaine meilleure action.</h1><p>RKJO utilise tes résultats, ton autonomie et ta rétention pour décider ce qui est le plus utile maintenant.</p></div><div className="rkjo-supports-privacy">Décision pédagogique explicable</div></header>
    {error?<div className="rkjo-session-error">{error}</div>:null}
    {!learnerId?<section className="rkjo-supports-workspace"><strong>Choisis ton profil étudiant pour démarrer.</strong></section>:
    !data?<section className="rkjo-supports-workspace">RKJO prépare ta recommandation…</section>:
    <><section className="rkjo-today-card"><div className="rkjo-today-copy"><span className="rkjo-edu-kicker">RECOMMANDATION RKJO · {data.rule_id}</span><h2>{data.target_competency ?? "Commencer ton parcours"}</h2><p>{data.explanation}</p><div className="rkjo-today-actions"><a className="rkjo-start" href={(()=>{const q=new URLSearchParams();if(learnerId)q.set("learnerId",learnerId);if(courseId)q.set("courseId",courseId);if(data.challenge_id)q.set("challengeId",data.challenge_id);const testActions=new Set(["positioning_test","request_proof","start_mock_exam"]);const base=testActions.has(data.action)?"/education/test":"/education/practice";return `${base}?${q.toString()}`;})()}>{actionLabels[data.action]??"Commencer"} →</a></div></div><div className="rkjo-session-visual"><div className="rkjo-session-ring"><strong>{data.rule_id}</strong><span>{data.policy_version}</span></div></div></section>
    <section className="rkjo-edu-summary"><article><span>Maîtrise</span><strong>{pct(data.mastery)}</strong></article><article><span>Autonomie</span><strong>{pct(data.autonomy)}</strong></article><article><span>Rétention</span><strong>{pct(data.retention)}</strong></article></section></>}
  </EducationShell>;
}
