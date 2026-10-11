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


def test_extracts_real_pdf_text_with_page_citation():
    """A valid in-memory PDF must actually yield a traceable course segment."""
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    from rkjo_education.curriculum.health_study_generator import make_revision_outline

    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    font_ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})
    })
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 50 700 Td (Anatomie du coeur) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    output = BytesIO()
    writer.write(output)

    source = ingest(output.getvalue())
    assert source.document_id == "cm-1"
    assert source.document_type is StudyDocumentType.CM
    assert len(source.segments) == 1
    assert source.segments[0].page == 1
    assert "Anatomie du coeur" in source.segments[0].text
    outline = make_revision_outline(source)
    assert outline.items[0].segment_ids == (source.segments[0].segment_id,)
    outline.validate_sources(source)
