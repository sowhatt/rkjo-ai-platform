"""Structured educational artifacts with strictly verified source references."""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from rkjo_education.curriculum.study_sources import StudySourcePackage


class StudyArtifactType(StrEnum):
    REVISION_NOTE = "revision_note"
    MIND_MAP = "mind_map"
    FLASHCARDS = "flashcards"
    QUIZ = "quiz"
    MOCK_EXAM = "mock_exam"


@dataclass(frozen=True, slots=True)
class SourcedLearningItem:
    title: str
    body: str
    segment_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.body.strip() or not self.segment_ids:
            raise ValueError("Study items require content and original source references")


@dataclass(frozen=True, slots=True)
class StudyArtifact:
    artifact_type: StudyArtifactType
    source_document_id: str
    source_version: int
    items: tuple[SourcedLearningItem, ...]
    generated_by: str
    is_official_exam: bool = False

    def validate_sources(self, source: StudySourcePackage) -> None:
        if self.source_document_id != source.document_id or self.source_version != source.version:
            raise ValueError("Artifact source version is stale or mismatched")
        if self.is_official_exam:
            raise ValueError("Generated artifacts must not claim to be official exams")
        if not self.items:
            raise ValueError("Empty study artifact")
        valid = {s.segment_id for s in source.segments}
        if any(ref not in valid for item in self.items for ref in item.segment_ids):
            raise ValueError("Unverifiable study artifact citation")
