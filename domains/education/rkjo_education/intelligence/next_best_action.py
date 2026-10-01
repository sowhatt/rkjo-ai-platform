from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class NextBestActionType(StrEnum):
    NEXT_ACTIVITY = "next_activity"
    REQUEST_PROOF = "request_proof"
    CONSOLIDATION = "consolidation"
    CONSOLIDATION_AND_ALERT = "consolidation_and_alert"


@dataclass(frozen=True, slots=True)
class NextBestAction:
    action: NextBestActionType
    reason: str


class NextBestActionService:
    """Deterministic V1 pedagogical decision policy.

    The engine uses observable outcome, autonomy, mastery and proof need.
    It deliberately stays provider-neutral and explainable.
    """

    def decide(
        self,
        *,
        correct: bool,
        autonomy_score: int,
        mastery: str,
        proof_required: bool,
        repeated_failures: int = 0,
    ) -> NextBestAction:
        if not correct:
            if repeated_failures >= 2:
                return NextBestAction(
                    NextBestActionType.CONSOLIDATION_AND_ALERT,
                    "Échecs répétés : consolidation et intervention professeur.",
                )
            return NextBestAction(
                NextBestActionType.CONSOLIDATION,
                "Réponse incorrecte : consolider avant de poursuivre.",
            )

        if proof_required or autonomy_score < 70 or mastery in {"developing", "provisional"}:
            return NextBestAction(
                NextBestActionType.REQUEST_PROOF,
                "Réussite à confirmer par une preuve autonome.",
            )

        return NextBestAction(
            NextBestActionType.NEXT_ACTIVITY,
            "Réussite autonome : poursuivre vers l’activité suivante.",
        )
