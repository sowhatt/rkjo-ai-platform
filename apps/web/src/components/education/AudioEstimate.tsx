"use client";

import { useState } from "react";

type Estimate = {
  minutes: number;
  plan: string;
  amount_cents: number;
  currency: string;
  estimation_only: boolean;
};

export default function AudioEstimate() {
  const [minutes, setMinutes] = useState(120);
  const [plan, setPlan] = useState("standard");
  const [quote, setQuote] = useState<Estimate | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function calculate() {
    setLoading(true);
    setError("");
    setQuote(null);
    try {
      const response = await fetch("/api/education/study/audio-estimate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ minutes, plan }),
        cache: "no-store",
      });
      const data: unknown = await response.json();
      if (!response.ok) {
        const detail = data && typeof data === "object" && "detail" in data
          ? String(data.detail) : "Estimation impossible.";
        throw new Error(detail);
      }
      setQuote(data as Estimate);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Service indisponible.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" aria-label="Estimer le résumé audio">
      <p className="text-xs font-bold uppercase tracking-widest text-blue-700">Tarification à la demande · simulation</p>
      <h2 className="mt-2 text-xl font-bold">Combien coûtera le résumé de mon cours audio ?</h2>
      <p className="mt-2 text-sm text-slate-600">
        Estime un prix de lancement avant d&apos;importer ton cours. Aucun paiement ni transcription n&apos;est déclenché.
      </p>
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-semibold">
          Durée estimée (minutes)
          <input type="number" min={1} max={600} step={1} value={minutes}
            onChange={(event) => { setMinutes(Number(event.target.value)); setQuote(null); }}
            className="mt-2 w-full rounded-lg border border-slate-300 p-3" />
        </label>
        <label className="text-sm font-semibold">
          Formule de résumé
          <select value={plan} onChange={(event) => { setPlan(event.target.value); setQuote(null); }}
            className="mt-2 w-full rounded-lg border border-slate-300 bg-white p-3">
            <option value="express">Express · notions essentielles</option>
            <option value="standard">Standard · résumé structuré</option>
            <option value="revision">Révision · résumé, flashcards, QCM</option>
          </select>
        </label>
      </div>
      <button type="button" disabled={loading} onClick={calculate}
        className="mt-4 rounded-xl bg-slate-900 px-6 py-3 text-sm font-semibold text-white disabled:opacity-50">
        {loading ? "Calcul en cours…" : "Estimer le prix"}
      </button>
      {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
      {quote && (
        <div className="mt-5 rounded-xl border border-blue-200 bg-blue-50 p-4" role="status">
          <p className="text-sm font-medium text-blue-900">Simulation pour {quote.minutes} min</p>
          <p className="mt-1 text-3xl font-bold text-blue-950">
            {(quote.amount_cents / 100).toLocaleString("fr-FR", { style: "currency", currency: quote.currency })}
          </p>
          <p className="mt-2 text-sm text-blue-900">
            Tarif indicatif non contractuel. Aucune commande créée, aucun paiement effectué et aucun résumé généré.
          </p>
        </div>
      )}
      <p className="mt-3 text-xs text-slate-500">
        Estimation basée sur des tranches de 120 minutes. Prix définitifs après mesure réelle des coûts techniques.
        Les enregistrements devront être autorisés.
      </p>
    </section>
  );
}
