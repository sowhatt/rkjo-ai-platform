"use client";

import { useRef, useState, type PointerEvent } from "react";

type Point = { x: number; y: number };
type Stroke = { points: Point[] };

export default function EducationDrawingBoard({ resetKey }: { resetKey: number }) {
  const [strokes, setStrokes] = useState<Stroke[]>([]);
  const [active, setActive] = useState<Stroke | null>(null);
  const [eraser, setEraser] = useState(false);
  const boardRef = useRef<SVGSVGElement>(null);
  const activePointerRef = useRef<number | null>(null);
  const resetRef = useRef(resetKey);

  if (resetRef.current !== resetKey) {
    resetRef.current = resetKey;
    if (strokes.length) setStrokes([]);
    if (active) setActive(null);
    activePointerRef.current = null;
  }

  function pointFromEvent(event: PointerEvent<SVGSVGElement>): Point | null {
    const rect = boardRef.current?.getBoundingClientRect();
    if (!rect || !rect.width || !rect.height) return null;
    return {
      x: Math.max(0, Math.min(600, ((event.clientX - rect.left) / rect.width) * 600)),
      y: Math.max(0, Math.min(260, ((event.clientY - rect.top) / rect.height) * 260)),
    };
  }

  function pointerDown(event: PointerEvent<SVGSVGElement>) {
    if (activePointerRef.current !== null) return;
    const point = pointFromEvent(event);
    if (!point) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    activePointerRef.current = event.pointerId;
    if (eraser) {
      setStrokes((old) => old.filter((stroke) => stroke.points.every((p) =>
        Math.hypot(p.x - point.x, p.y - point.y) > 20)));
      return;
    }
    setActive({ points: [point] });
  }

  function pointerMove(event: PointerEvent<SVGSVGElement>) {
    if (activePointerRef.current !== event.pointerId || eraser) return;
    const point = pointFromEvent(event);
    if (!point) return;
    setActive((old) => old ? { points: [...old.points, point] } : old);
  }

  function pointerEnd(event: PointerEvent<SVGSVGElement>) {
    if (activePointerRef.current !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    activePointerRef.current = null;
    setActive((stroke) => {
      if (stroke) setStrokes((old) => [...old, stroke]);
      return null;
    });
  }

  function path(stroke: Stroke) {
    const points = stroke.points;
    if (!points.length) return "";
    if (points.length === 1) {
      const p = points[0];
      return `M ${p.x} ${p.y} l 0.1 0`;
    }
    return points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold">Mon ardoise tactile</h3>
        <div className="flex flex-wrap gap-2">
          <button type="button" aria-pressed={!eraser} onClick={() => setEraser(false)}
            className={`rounded-lg px-3 py-2 text-sm ${!eraser ? "bg-blue-700 text-white" : "border border-slate-300"}`}>Crayon</button>
          <button type="button" aria-pressed={eraser} onClick={() => setEraser(true)}
            className={`rounded-lg px-3 py-2 text-sm ${eraser ? "bg-blue-700 text-white" : "border border-slate-300"}`}>Gomme</button>
          <button type="button" onClick={() => setStrokes((old) => old.slice(0, -1))} disabled={!strokes.length}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:opacity-40">Annuler</button>
          <button type="button" onClick={() => { setStrokes([]); setActive(null); }} disabled={!strokes.length && !active}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:opacity-40">Effacer</button>
        </div>
      </div>
      <svg ref={boardRef} viewBox="0 0 600 260" role="img" aria-label="Ardoise de dessin libre. Dessine au doigt, au stylet ou à la souris."
        onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerEnd}
        onPointerCancel={pointerEnd} onLostPointerCapture={() => { activePointerRef.current = null; setActive(null); }}
        className="w-full cursor-crosshair rounded-xl border border-slate-300 bg-white"
        style={{ touchAction: "none", userSelect: "none" }}>
        <path d="M0 65 H600 M0 130 H600 M0 195 H600" stroke="#e2e8f0" strokeWidth="1" />
        {[...strokes, ...(active ? [active] : [])].map((stroke, index) => (
          <path key={index} d={path(stroke)} fill="none" stroke="#1d4ed8" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
        ))}
      </svg>
      <p className="text-xs text-slate-500">Gomme : retire un trait touché près de son point de départ ou de son tracé. Pour écrire au clavier, utilise le brouillon texte. Aucun dessin n&apos;est envoyé au serveur.</p>
    </div>
  );
}
