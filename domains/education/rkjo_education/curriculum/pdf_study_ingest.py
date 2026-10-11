"""Local PDF text ingestion for university CM/TD/TP study sources.

This is a pure extraction adapter, not a public upload endpoint. File authorization,
malware screening, size enforcement and persistence belong at the authenticated API.
Scanned or image-only PDF pages require a separate OCR/vision pipeline.
"""
from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader

from rkjo_education.curriculum.study_sources import (
    StudyDocumentType,
    StudySegment,
    StudySourcePackage,
)


class StudyPdfError(ValueError):
    """PDF cannot safely produce a usable text source."""


def extract_study_pdf(
    *,
    pdf_bytes: bytes,
    tenant_id: str,
    learner_id: str,
    programme_id: str,
    ue_id: str,
    document_id: str,
    document_type: StudyDocumentType,
    version: int = 1,
    max_bytes: int = 15 * 1024 * 1024,
    max_pages: int = 150,
) -> StudySourcePackage:
    if not isinstance(pdf_bytes, bytes) or not pdf_bytes.startswith(b"%PDF-"):
        raise StudyPdfError("A PDF byte stream is required")
    if len(pdf_bytes) > max_bytes or len(pdf_bytes) < 8:
        raise StudyPdfError("PDF size is outside the permitted range")
    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=True)
        if reader.is_encrypted:
            raise StudyPdfError("Encrypted PDF is unsupported")
        if not 1 <= len(reader.pages) <= max_pages:
            raise StudyPdfError("Unsupported PDF page count")
        segments = []
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                segments.append(
                    StudySegment.from_text(document_id=document_id, page=index, text=text)
                )
    except StudyPdfError:
        raise
    except Exception as exc:
        raise StudyPdfError("PDF parsing failed") from exc
    if not segments:
        raise StudyPdfError("No extractable text; OCR required")
    return StudySourcePackage(
        tenant_id=tenant_id,
        learner_id=learner_id,
        programme_id=programme_id,
        ue_id=ue_id,
        document_id=document_id,
        version=version,
        document_type=StudyDocumentType(document_type),
        segments=tuple(segments),
    )
