export const audioPrices = { express: 149, standard: 249, revision: 399 } as const;
export type AudioPlan = keyof typeof audioPrices;

export function audioEstimate(minutes: number, plan: AudioPlan) {
  if (!Number.isInteger(minutes) || minutes < 1 || minutes > 600) throw new Error("Durée invalide");
  if (!Object.prototype.hasOwnProperty.call(audioPrices, plan)) throw new Error("Formule inconnue");
  return {
    minutes,
    plan,
    amount_cents: audioPrices[plan] * Math.ceil(minutes / 120),
    currency: "EUR",
    estimation_only: true,
    payment_enabled: false,
  };
}
