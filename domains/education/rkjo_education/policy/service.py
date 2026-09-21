from __future__ import annotations

from .models import (
    AssistanceLevel,
    LearningMode,
    LearningPolicyDecision,
)


class LearningPolicyService:
    """Deterministic rules controlling how much help the tutor may provide."""

    def decide(
        self,
        *,
        mode: LearningMode,
        requested_assistance: AssistanceLevel | None = None,
    ) -> LearningPolicyDecision:
        if mode is LearningMode.EXAM:
            return LearningPolicyDecision(
                mode=mode,
                assistance_level=AssistanceLevel.NONE,
                allow_direct_answer=False,
                require_verification=False,
                instruction=(
                    "Mode examen. Ne donne aucune aide, aucun indice "
                    "et aucune solution. Invite uniquement l'élève à répondre."
                ),
            )

        if mode is LearningMode.SOCRATIC:
            return LearningPolicyDecision(
                mode=mode,
                assistance_level=AssistanceLevel.SOCRATIC_QUESTION,
                allow_direct_answer=False,
                require_verification=True,
                instruction=(
                    "Ne donne pas la solution. Pose une question courte "
                    "qui aide l'élève à trouver lui-même la prochaine étape."
                ),
            )

        maximum = (
            AssistanceLevel.GUIDED_METHOD
            if mode is LearningMode.GUIDED
            else AssistanceLevel.EXPLAINED_SOLUTION
        )

        requested = (
            requested_assistance
            if requested_assistance is not None
            else AssistanceLevel.LIGHT_HINT
        )

        effective = AssistanceLevel(
            min(int(requested), int(maximum))
        )

        allow_direct_answer = (
            effective >= AssistanceLevel.EXPLAINED_SOLUTION
        )

        instructions = {
            AssistanceLevel.NONE:
                "N'apporte aucune aide. Demande à l'élève de répondre.",
            AssistanceLevel.SOCRATIC_QUESTION:
                "Pose une question guidante sans révéler la solution.",
            AssistanceLevel.LIGHT_HINT:
                "Donne un indice léger sans révéler la méthode complète.",
            AssistanceLevel.STRONG_HINT:
                "Donne un indice précis mais laisse l'élève terminer.",
            AssistanceLevel.GUIDED_METHOD:
                "Guide la méthode étape par étape sans donner immédiatement le résultat final.",
            AssistanceLevel.EXPLAINED_SOLUTION:
                "Explique la solution puis termine par une question de vérification.",
        }

        return LearningPolicyDecision(
            mode=mode,
            assistance_level=effective,
            allow_direct_answer=allow_direct_answer,
            require_verification=True,
            instruction=instructions[effective],
        )
