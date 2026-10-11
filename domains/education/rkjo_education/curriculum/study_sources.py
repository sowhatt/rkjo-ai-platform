"""Versioned course-source contract for medical, pharmacy and nursing studies.

Text segments must come from a trusted extraction step; this module does not
parse PDF files or imply that extracted content is an official curriculum.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256


class StudyDocumentType(StrEnum):
    CM = "cm"
    TD = "td"
    TP = "tp"
    NOTES = "notes"
    EXERCISES = "exercises"
    CORRECTION = "correction"
    ANNALS = "annals"


@dataclass(frozen=True, slots=True)
class StudySegment:
    segment_id: str
    page: int
    text: str
    content_hash: str

    @classmethod
    def from_text(cls, *, document_id: str, page: int, text: str) -> "StudySegment":
        if not document_id.strip() or page < 1 or not text.strip():
            raise ValueError("Document, page and nonempty extracted text are required")
        digest = sha256(text.encode("utf-8")).hexdigest()
        return cls(f"{document_id}:p{page}:{digest[:12]}", page, text, digest)


@dataclass(frozen=True, slots=True)
class StudySourcePackage:
    tenant_id: str
    learner_id: str
    programme_id: str
    ue_id: str
    document_id: str
    version: int
    document_type: StudyDocumentType
    segments: tuple[StudySegment, ...]

    def __post_init__(self) -> None:
        for key in ("tenant_id", "learner_id", "programme_id", "ue_id", "document_id"):
            if not getattr(self, key).strip():
                raise ValueError(f"{key} required")
        if self.version < 1 or not self.segments:
            raise ValueError("Version >=1 and at least one extracted segment required")
        if len({segment.segment_id for segment in self.segments}) != len(self.segments):
            raise ValueError("Duplicate source segment")

    def segment(self, segment_id: str) -> StudySegment:
        return next(segment for segment in self.segments if segment.segment_id == segment_id)
