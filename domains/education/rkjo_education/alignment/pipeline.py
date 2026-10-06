from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from .models import AlignmentDecision, ReferentialCompetency
from .service import EducationAlignmentService


@dataclass(frozen=True, slots=True)
class SourceSegment:
    source_id: UUID
    segment_ref: str
    text: str


@dataclass(frozen=True, slots=True)
class SegmentAlignment:
    segment_ref: str
    decision: AlignmentDecision


class EducationAlignmentPipeline:
    """Align source segments independently so one uncertain question cannot taint another."""

    def __init__(self, service: EducationAlignmentService | None = None) -> None:
        self.service = service or EducationAlignmentService()

    def align_segments(
        self,
        segments: list[SourceSegment],
        referential: list[ReferentialCompetency],
    ) -> list[SegmentAlignment]:
        return [
            SegmentAlignment(
                segment_ref=segment.segment_ref,
                decision=self.service.align(
                    source_id=segment.source_id,
                    text=segment.text,
                    referential=referential,
                ),
            )
            for segment in segments
        ]

    @staticmethod
    def accepted_competencies(results: list[SegmentAlignment]) -> set[str]:
        return {
            result.decision.candidate.competency_code
            for result in results
            if result.decision.candidate is not None
            and not result.decision.requires_learner_confirmation
        }
