"""MM-RAG-02: mixed PDF OCR port contract and boundary checks."""
from types import SimpleNamespace

import pytest

from rkjo_kernel.rag.multimodal_ocr import (
    MixedPDFEvidenceExtractor, OCRPageResult,
)


class FakeOCR:
    def __init__(self, *, text="Garantie dentaire 400 EUR", tenant=None,
                 document=None, page=None):
        self.text, self.tenant, self.document, self.page = text, tenant, document, page
        self.calls = []

    def recognize_page(self, *, pdf_path, tenant_id, document_id, page_number):
        self.calls.append((tenant_id, document_id, page_number))
        return OCRPageResult(
            tenant_id=self.tenant or tenant_id,
            document_id=self.document or document_id,
            page_number=self.page or page_number,
            text=self.text,
            confidence=0.9,
        )


def fixture_pdf(monkeypatch, tmp_path, pages):
    import rkjo_kernel.rag.multimodal_ocr as module
    source = tmp_path / "contract.pdf"
    source.write_bytes(b"%PDF-fixture")
    monkeypatch.setattr(
        module, "PdfReader",
        lambda path: SimpleNamespace(pages=[
            SimpleNamespace(extract_text=lambda text=text: text) for text in pages
        ]),
    )
    return source


def test_mixed_pdf_only_scanned_page_calls_ocr(monkeypatch, tmp_path):
    source = fixture_pdf(monkeypatch, tmp_path, [
        "Hospitalisation : 100%", "", "Optique : 300 EUR",
    ])
    ocr = FakeOCR()
    result = MixedPDFEvidenceExtractor(ocr).extract(
        source, tenant_id="tenant-a", document_id="contrat-7",
    )
    assert result.complete
    assert result.page_count == 3
    assert result.ocr_pages == (2,)
    assert result.rejected_pages == ()
    assert ocr.calls == [("tenant-a", "contrat-7", 2)]
    assert [b.location.page_number for b in result.document.blocks] == [1, 2, 3]
    assert [b.extraction_method.value for b in result.document.blocks] == [
        "native_text", "ocr", "native_text",
    ]
    citation = result.document.citation("p2-ocr", tenant_id="tenant-a")
    assert citation["page_number"] == 2
    assert citation["extraction_method"] == "ocr"


def test_fully_scanned_pdf_supported_with_ocr_port(monkeypatch, tmp_path):
    source = fixture_pdf(monkeypatch, tmp_path, ["", ""])
    ocr = FakeOCR()
    result = MixedPDFEvidenceExtractor(ocr).extract(
        source, tenant_id="tenant-a", document_id="doc",
    )
    assert result.ocr_pages == (1, 2)
    assert result.complete


@pytest.mark.parametrize("overrides", [
    {"tenant": "other-tenant"},
    {"document": "other-doc"},
    {"page": 5},
])
def test_ocr_mismatched_provenance_is_rejected(monkeypatch, tmp_path, overrides):
    source = fixture_pdf(monkeypatch, tmp_path, [""])
    ocr = FakeOCR(**overrides)
    with pytest.raises(PermissionError):
        MixedPDFEvidenceExtractor(ocr).extract(
            source, tenant_id="tenant-a", document_id="doc",
        )


def test_blank_ocr_fails_closed(monkeypatch, tmp_path):
    source = fixture_pdf(monkeypatch, tmp_path, ["valid native", ""])
    ocr = FakeOCR(text=" ")
    with pytest.raises(ValueError, match="incomplete evidence refused"):
        MixedPDFEvidenceExtractor(ocr).extract(
            source, tenant_id="tenant-a", document_id="doc",
        )


def test_incomplete_result_is_explicit(monkeypatch, tmp_path):
    source = fixture_pdf(monkeypatch, tmp_path, ["valid native", ""])
    result = MixedPDFEvidenceExtractor(FakeOCR(text=" ")).extract(
        source, tenant_id="tenant-a", document_id="doc",
        allow_incomplete=True,
    )
    assert not result.complete
    assert result.rejected_pages == (2,)
    assert result.ocr_pages == ()


def test_size_limits_before_ocr(monkeypatch, tmp_path):
    source = fixture_pdf(monkeypatch, tmp_path, ["A" * 51, ""])
    ocr = FakeOCR()
    with pytest.raises(ValueError, match="size limit"):
        MixedPDFEvidenceExtractor(ocr, max_chars_per_page=50).extract(
            source, tenant_id="tenant-a", document_id="doc",
        )
    assert ocr.calls == []


def test_page_limit_before_ocr(monkeypatch, tmp_path):
    source = fixture_pdf(monkeypatch, tmp_path, ["", ""])
    ocr = FakeOCR()
    with pytest.raises(ValueError, match="page limit"):
        MixedPDFEvidenceExtractor(ocr, max_pages=1).extract(
            source, tenant_id="tenant-a", document_id="doc",
        )
    assert ocr.calls == []


@pytest.mark.parametrize("confidence", [-0.1, 1.1, True])
def test_invalid_confidence(confidence):
    with pytest.raises(ValueError):
        OCRPageResult("tenant-a", "doc", 1, "recognized", confidence)


def test_no_tenant_is_rejected_before_ocr(monkeypatch, tmp_path):
    source = fixture_pdf(monkeypatch, tmp_path, [""])
    ocr = FakeOCR()
    with pytest.raises(ValueError, match="tenant"):
        MixedPDFEvidenceExtractor(ocr).extract(
            source, tenant_id="", document_id="doc",
        )
    assert ocr.calls == []
