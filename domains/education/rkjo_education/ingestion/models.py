from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class DocumentKind(StrEnum):
    COURSE = "course"
    TD = "td"
    CORRECTED_COPY = "corrected_copy"
    EXAM = "exam"
    OTHER = "other"


class Provenance(StrEnum):
    LEARNER_UPLOAD = "learner_upload"
    TEACHER_MATERIAL = "teacher_material"
    RKJO_GENERATED = "rkjo_generated"


class EducationDocument(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    learner_id: UUID
    filename: str
    media_type: str
    kind: DocumentKind
    provenance: Provenance
    extracted_text: str
    source_hash: str
