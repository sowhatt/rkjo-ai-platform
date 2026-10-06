from __future__ import annotations

from hashlib import sha256
from uuid import UUID

from .models import DocumentKind, EducationDocument, Provenance


class EducationIngestionService:
    """Learner-first ingestion boundary. Extraction adapters stay outside the domain."""

    SUPPORTED_MEDIA_TYPES = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "text/plain",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    def ingest(
        self,
        *,
        tenant_id: UUID,
        learner_id: UUID,
        filename: str,
        media_type: str,
        extracted_text: str,
        kind: DocumentKind,
        provenance: Provenance = Provenance.LEARNER_UPLOAD,
    ) -> EducationDocument:
        if media_type not in self.SUPPORTED_MEDIA_TYPES:
            raise ValueError("unsupported education document media type")
        text = extracted_text.strip()
        if not text:
            raise ValueError("extracted education document text is empty")
        digest = sha256((filename + "\n" + text).encode("utf-8")).hexdigest()
        return EducationDocument(
            tenant_id=tenant_id,
            learner_id=learner_id,
            filename=filename,
            media_type=media_type,
            kind=kind,
            provenance=provenance,
            extracted_text=text,
            source_hash=digest,
        )
