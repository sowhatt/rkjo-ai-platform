"""Local PDF parsing contract tests; no external service or patient data."""
from io import BytesIO

import pytest
from pypdf import PdfWriter

from rkjo_education.curriculum.pdf_study_ingest import StudyPdfError, extract_study_pdf
from rkjo_education.curriculum.study_sources import StudyDocumentType


def pdf(*, pages=1, encrypted=False):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    if encrypted:
        writer.encrypt("test-password")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def ingest(data, **kwargs):
    return extract_study_pdf(
        pdf_bytes=data,
        tenant_id="university-1",
        learner_id="student-1",
        programme_id="medicine-year-1",
        ue_id="anatomy",
        document_id="cm-1",
        document_type=StudyDocumentType.CM,
        **kwargs,
    )


def test_rejects_non_pdf_bytes():
    with pytest.raises(StudyPdfError, match="PDF byte stream"):
        ingest(b"not a PDF")


def test_rejects_image_only_or_blank_pdf_for_ocr():
    with pytest.raises(StudyPdfError, match="OCR required"):
        ingest(pdf())


def test_rejects_encrypted_pdf():
    with pytest.raises(StudyPdfError, match="Encrypted"):
        ingest(pdf(encrypted=True))


def test_rejects_page_limit():
    with pytest.raises(StudyPdfError, match="page count"):
        ingest(pdf(pages=2), max_pages=1)


def test_rejects_byte_limit():
    with pytest.raises(StudyPdfError, match="size"):
        ingest(pdf(), max_bytes=10)


def test_invalid_pdf_structure():
    with pytest.raises(StudyPdfError):
        ingest(b"%PDF-not-a-valid-document")
