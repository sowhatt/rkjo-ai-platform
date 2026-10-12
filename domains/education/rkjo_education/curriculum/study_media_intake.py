"""Admission contract for lecture recordings and digital textbooks.

Actual transcription, OCR, translation and storage are async downstream stages.
Use permission/consent checks at upload API as well as this boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


MIB = 1024 * 1024
BOOK_MAX_BYTES = 50 * MIB
AUDIO_MAX_BYTES = 50 * MIB


class SourceKind(StrEnum):
    LECTURE_AUDIO = "lecture_audio"
    DIGITAL_BOOK = "digital_book"


class SourceLanguage(StrEnum):
    ENGLISH = "en"
    FRENCH = "fr"
    UNKNOWN = "und"


class IntakeState(StrEnum):
    AWAITING_UPLOAD = "awaiting_upload"
    AWAITING_TRANSCRIPTION = "awaiting_transcription"
    AWAITING_EXTRACTION = "awaiting_extraction"
    AWAITING_TRANSLATION = "awaiting_translation"
    READY = "ready"
    NEEDS_REVIEW = "needs_review"


@dataclass(frozen=True, slots=True)
class StudyMediaRequest:
    tenant_id: str
    learner_id: str
    ue_id: str
    kind: SourceKind
    filename: str
    size_bytes: int
    content_type: str
    language: SourceLanguage
    translation_to_french: bool = False
    rights_confirmed: bool = False
    recording_consent_confirmed: bool = False

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (
            self.tenant_id, self.learner_id, self.ue_id, self.filename
        )):
            raise ValueError("Student, tenant, UE and filename are required")
        if not self.rights_confirmed:
            raise ValueError("Right to use material must be confirmed")
        if self.size_bytes < 1 or self.size_bytes > 50 * MIB:
            raise ValueError("Source exceeds the 50 MiB maximum")
        if self.kind is SourceKind.DIGITAL_BOOK:
            if self.content_type not in {"application/pdf", "application/epub+zip"}:
                raise ValueError("Book must be PDF or EPUB")
        elif self.kind is SourceKind.LECTURE_AUDIO:
            if self.content_type not in {
                "audio/mpeg", "audio/mp4", "audio/wav", "audio/x-wav",
                "audio/webm", "audio/ogg",
            }:
                raise ValueError("Unsupported lecture audio type")
            if not self.recording_consent_confirmed:
                raise ValueError("Recording permission must be confirmed")
        else:
            raise ValueError("Unsupported source kind")
        if self.translation_to_french and self.language is not SourceLanguage.ENGLISH:
            raise ValueError("French translation requires English source selection")

    @property
    def initial_state(self) -> IntakeState:
        if self.kind is SourceKind.LECTURE_AUDIO:
            return IntakeState.AWAITING_TRANSCRIPTION
        return IntakeState.AWAITING_EXTRACTION
