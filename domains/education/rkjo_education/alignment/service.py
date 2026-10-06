from __future__ import annotations

from uuid import UUID

from .models import AlignmentCandidate, AlignmentDecision, ReferentialCompetency


class EducationAlignmentService:
    """Deterministic V1 alignment against a preloaded referential."""

    CONFIRMATION_THRESHOLD = 0.70

    def align(
        self,
        *,
        source_id: UUID,
        text: str,
        referential: list[ReferentialCompetency],
    ) -> AlignmentDecision:
        normalized = text.casefold()
        ranked: list[tuple[float, ReferentialCompetency, list[str]]] = []
        for competency in referential:
            hits = [kw for kw in competency.keywords if kw.casefold() in normalized]
            denominator = max(1, len(competency.keywords))
            confidence = min(1.0, len(hits) / denominator)
            if hits:
                ranked.append((confidence, competency, hits))
        if not ranked:
            return AlignmentDecision(source_id=source_id, candidate=None, requires_learner_confirmation=True)
        confidence, competency, hits = max(ranked, key=lambda item: (item[0], item[1].importance))
        candidate = AlignmentCandidate(
            competency_code=competency.code,
            confidence=confidence,
            reason="keywords:" + ",".join(hits),
        )
        return AlignmentDecision(
            source_id=source_id,
            candidate=candidate,
            requires_learner_confirmation=confidence < self.CONFIRMATION_THRESHOLD,
        )

    def confirm(self, decision: AlignmentDecision, *, competency_code: str) -> AlignmentDecision:
        candidate = AlignmentCandidate(
            competency_code=competency_code,
            confidence=1.0,
            reason="learner_confirmed",
        )
        return AlignmentDecision(
            source_id=decision.source_id,
            candidate=candidate,
            requires_learner_confirmation=False,
        )
