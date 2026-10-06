from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from rkjo_education.alignment import EducationAlignmentService, ReferentialCompetency
from rkjo_education.intelligence.corrected_copy import CorrectedQuestionEvidence

from .corrected_copy import CorrectedCopySplitter


@dataclass(frozen=True, slots=True)
class AlignedCorrectedQuestion:
    question_ref: str
    competency_code: str | None
    alignment_confidence: float
    requires_confirmation: bool
    evidence: CorrectedQuestionEvidence | None


class CorrectedCopyAlignmentService:
    """Turn an uploaded corrected copy into per-question, competency-scoped evidence."""

    def __init__(self) -> None:
        self.splitter = CorrectedCopySplitter()
        self.aligner = EducationAlignmentService()

    def process(
        self,
        *,
        text: str,
        referential: list[ReferentialCompetency],
        source_id: UUID | None = None,
    ) -> list[AlignedCorrectedQuestion]:
        source = source_id or uuid4()
        result: list[AlignedCorrectedQuestion] = []
        for block in self.splitter.split(text):
            decision = self.aligner.align(
                source_id=source,
                text=block.body,
                referential=referential,
            )
            candidate = decision.candidate
            competency_code = candidate.competency_code if candidate else None
            confidence = candidate.confidence if candidate else 0.0
            evidence = None
            if (
                competency_code is not None
                and block.earned_points is not None
                and block.max_points is not None
            ):
                evidence = CorrectedQuestionEvidence(
                    competency_code=competency_code,
                    earned_points=block.earned_points,
                    max_points=block.max_points,
                    alignment_confidence=confidence,
                )
            result.append(AlignedCorrectedQuestion(
                question_ref=block.question_ref,
                competency_code=competency_code,
                alignment_confidence=confidence,
                requires_confirmation=decision.requires_learner_confirmation,
                evidence=evidence,
            ))
        return result
