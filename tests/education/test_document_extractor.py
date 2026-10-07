from io import BytesIO
from zipfile import ZipFile

import pytest
from pypdf import PdfWriter

from rkjo_education.ingestion.extractor import DocumentExtractionError, EducationDocumentExtractor


def test_extracts_plain_text():
    text = EducationDocumentExtractor().extract(
        filename="cours.txt", media_type="text/plain", content=b"Cellule et membrane"
    )
    assert text == "Cellule et membrane"


def test_extracts_docx_without_extra_runtime_dependency():
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>ADN et chromosome</w:t></w:r></w:p></w:body></w:document>",
        )
    text = EducationDocumentExtractor().extract(
        filename="cours.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        content=buffer.getvalue(),
    )
    assert text == "ADN et chromosome"


def test_image_fails_explicitly_until_ocr_is_connected():
    with pytest.raises(DocumentExtractionError, match="OCR"):
        EducationDocumentExtractor().extract(
            filename="copie.jpg", media_type="image/jpeg", content=b"not-an-image"
        )
