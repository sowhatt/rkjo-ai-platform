"""MM-RAG-01: provenance and privacy regression tests."""
from types import SimpleNamespace

import pytest

from rkjo_kernel.rag.multimodal_evidence import (
    EvidenceBlock, EvidenceDocument, EvidenceKind, EvidenceLocation,
    ExtractionMethod,
)
from rkjo_kernel.rag.multimodal_pdf import NativePDFEvidenceExtractor


def block(identifier="p1-text", page=1):
    return EvidenceBlock(
        block_id=identifier, kind=EvidenceKind.TEXT, text="Garantie optique 200 EUR",
        extraction_method=ExtractionMethod.NATIVE_TEXT,
        location=EvidenceLocation(page_number=page),
    )


def test_page_level_citation_and_tenant_isolation():
    document = EvidenceDocument(
        tenant_id="mutuelle-a", document_id="contrat-1",
        source_type="pdf", blocks=(block(),),
    )
    citation = document.citation("p1-text", tenant_id="mutuelle-a")
    assert citation["page_number"] == 1
    assert citation["extraction_method"] == "native_text"
    with pytest.raises(PermissionError):
        document.citation("p1-text", tenant_id="mutuelle-b")
    with pytest.raises(LookupError):
        document.citation("unknown", tenant_id="mutuelle-a")


def test_image_reference_is_not_falsely_text_searchable():
    image = EvidenceBlock(
        block_id="p2-image", kind=EvidenceKind.IMAGE, text="",
        extraction_method=ExtractionMethod.VLM,
        location=EvidenceLocation(page_number=2),
        asset_ref="artifact-42",
    )
    doc = EvidenceDocument("tenant-a", "d1", "pdf", (block(), image))
    assert doc.searchable_blocks() == (doc.blocks[0],)


@pytest.mark.parametrize("location", [
    EvidenceLocation(page_number=1, bounding_box=(0.1,0.2,0.7,0.8)),
    EvidenceLocation(start_ms=100,end_ms=900),
])
def test_valid_spatial_and_temporal_locations(location):
    assert location is not None


@pytest.mark.parametrize("params", [
    {"page_number":0},
    {"start_ms":5},
    {"start_ms":-1, "end_ms":6},
    {"start_ms":10, "end_ms":10},
    {"page_number":1,"bounding_box":(0.8,0.1,0.2,0.9)},
    {"bounding_box":(0.1,0.1,0.9,0.9)},
])
def test_invalid_locations_rejected(params):
    with pytest.raises(ValueError):
        EvidenceLocation(**params)


def test_duplicate_evidence_ids_rejected():
    with pytest.raises(ValueError):
        EvidenceDocument("tenant-a", "d1", "pdf", (block(), block()))


def test_no_opaque_external_url_in_asset_ref():
    with pytest.raises(ValueError):
        EvidenceBlock(
            block_id="p1-img", kind=EvidenceKind.IMAGE, text="",
            extraction_method=ExtractionMethod.VLM,
            location=EvidenceLocation(page_number=1),
            asset_ref="https://external.example/path",
        )


def test_pdf_extractor_keeps_page_and_flags_missing_ocr(monkeypatch, tmp_path):
    import rkjo_kernel.rag.multimodal_pdf as module
    pdf = tmp_path / "contract.pdf"
    pdf.write_bytes(b"%PDF-test-stub")
    class Reader:
        def __init__(self, path):
            self.pages = [
                SimpleNamespace(extract_text=lambda: "Garantie hospitalisation"),
                SimpleNamespace(extract_text=lambda: ""),
                SimpleNamespace(extract_text=lambda: "Plafond optique"),
            ]
    monkeypatch.setattr(module, "PdfReader", Reader)
    inspection = NativePDFEvidenceExtractor().inspect(
        pdf, tenant_id="a", document_id="doc",
    )
    assert [b.location.page_number for b in inspection["document"].blocks] == [1,3]
    assert inspection["pages_needing_ocr"] == (2,)


def test_all_scanned_pdf_fails_closed(monkeypatch, tmp_path):
    import rkjo_kernel.rag.multimodal_pdf as module
    pdf = tmp_path / "scanned.pdf"
    pdf.write_bytes(b"%PDF-test-stub")
    monkeypatch.setattr(module, "PdfReader",
                        lambda path: SimpleNamespace(pages=[
                            SimpleNamespace(extract_text=lambda: ""),
                        ]))
    with pytest.raises(ValueError, match="OCR processing is required"):
        NativePDFEvidenceExtractor().extract(pdf, tenant_id="a", document_id="doc")
