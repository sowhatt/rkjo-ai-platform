"use client";
import { FormEvent, useState } from "react";
import { useSearchParams } from "next/navigation";
import EducationShell from "@/components/education/EducationShell";

export default function EducationPractice(){
 const params=useSearchParams(); const learnerId=params.get("learnerId")??""; const courseId=params.get("courseId")??"";
 const [exercise,setExercise]=useState(""); const [answer,setAnswer]=useState(""); const [level,setLevel]=useState(0); const [assessmentId,setAssessmentId]=useState(""); const [busy,setBusy]=useState(false); const [error,setError]=useState("");
 async function ask(e:FormEvent){e.preventDefault(); if(!learnerId||!courseId||!exercise.trim())return; setBusy(true);setError("");
  try{const r=await fetch("/api/education/tutor/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({learner_id:learnerId,course_id:courseId,question:exercise,mode:"practice",requested_assistance:level===0?null:`hint_${level}`})});
   const p=await r.json(); if(!r.ok)throw new Error(p.detail??"Aide indisponible"); setAnswer(p.answer??"");}
  catch(e){setError(e instanceof Error?e.message:"Aide indisponible");}finally{setBusy(false);}
 }
 async function loadRealExercise(){if(!courseId)return;setBusy(true);setError("");try{const r=await fetch(`/api/education/courses/${encodeURIComponent(courseId)}/assessments`,{cache:"no-store"});const p=await r.json();if(!r.ok)throw new Error(p.detail??"Exercices indisponibles");const a=p?.[0];const q=a?.questions?.[0];if(!a||!q)throw new Error("Aucun exercice réel n’est encore associé à ce cours.");setAssessmentId(a.id);setExercise(q.prompt);}catch(e){setError(e instanceof Error?e.message:"Exercices indisponibles");}finally{setBusy(false)}}
 return <EducationShell active="practice"><header className="rkjo-demo-header"><div><span className="rkjo-edu-kicker">S’ENTRAÎNER</span><h1>Travaille un vrai exercice, sans recevoir la solution trop tôt.</h1><p>RKJO augmente progressivement l’aide. Chaque niveau d’aide pourra alimenter ton autonomie.</p></div></header>
 <section className="rkjo-supports-workspace"><div className="rkjo-today-actions"><button type="button" onClick={loadRealExercise} disabled={busy||!courseId}>Charger un exercice de mon cours</button>{assessmentId?<small>Exercice enseignant chargé · {assessmentId.slice(0,8)}</small>:null}</div><form onSubmit={ask}><label>Ton exercice ou la question du TD</label><textarea value={exercise} onChange={e=>setExercise(e.target.value)} rows={6} placeholder="Colle ici l’énoncé donné par ton enseignant…"/><div className="rkjo-today-actions"><button type="button" onClick={()=>setLevel(Math.min(3,level+1))}>Indice niveau {Math.min(3,level+1)}</button><button className="rkjo-start" disabled={busy||!learnerId||!courseId}>{busy?"RKJO analyse…":level?"Obtenir cet indice":"Commencer sans aide"}</button></div></form>
 {level>0?<p>Aide demandée : niveau {level}/3. La solution complète reste masquée.</p>:null}{error?<div className="rkjo-session-error">{error}</div>:null}{answer?<article className="rkjo-supports-workspace"><span className="rkjo-edu-kicker">PROFESSEUR IA · AIDE {level||1}</span><p>{answer}</p></article>:null}</section></EducationShell>;
}