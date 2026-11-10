"""MM-RAG-04.1: visual extraction contract and cross-tenant refusals."""
from dataclasses import replace

import pytest

from rkjo_kernel.rag.multimodal_evidence import (
    EvidenceBlock, EvidenceDocument, EvidenceKind, EvidenceLocation,
    ExtractionMethod,
)
from rkjo_kernel.rag.visual_evidence import (
    VisualEvidenceExtractor, VisualRegion, VisualResult,
)


def document():
    return EvidenceDocument(
        tenant_id="tenant-a", document_id="doc-a", source_type="pdf",
        blocks=(EvidenceBlock(
            block_id="p1-text", kind=EvidenceKind.TEXT, text="Invoice",
            extraction_method=ExtractionMethod.NATIVE_TEXT,
            location=EvidenceLocation(page_number=1),
        ),),
    )


def region(kind=EvidenceKind.TABLE):
    return VisualRegion(
        block_id="p1-table", asset_ref="asset-12", kind=kind,
        page_number=1, bounding_box=(0.1, 0.2, 0.8, 0.9),
    )


class StubPort:
    def __init__(self, transform=None):
        self.calls = []
        self.transform = transform

    def analyze(self, *, tenant_id, document_id, region):
        self.calls.append((tenant_id, document_id, region))
        result = VisualResult(
            tenant_id, document_id, region.block_id, region.asset_ref,
            region.kind, region.page_number, region.bounding_box,
            "Total: 250 EUR", 0.92,
        )
        return self.transform(result) if self.transform else result


def test_visual_enrichment_preserves_original_and_citations():
    port = StubPort()
    original = document()
    enriched = VisualEvidenceExtractor(port).enrich(
        original, tenant_id="tenant-a", regions=(region(),),
    )
    assert len(original.blocks) == 1
    assert len(enriched.blocks) == 2
    assert enriched.searchable_blocks()[-1].text == "Total: 250 EUR"
    citation = enriched.citation("p1-table", tenant_id="tenant-a")
    assert citation["kind"] == "table"
    assert citation["asset_ref"] == "asset-12"
    assert citation["bounding_box"] == (0.1, 0.2, 0.8, 0.9)
    assert port.calls[0][0:2] == ("tenant-a", "doc-a")


def test_no_cross_tenant_dispatch():
    port = StubPort()
    with pytest.raises(PermissionError):
        VisualEvidenceExtractor(port).enrich(
            document(), tenant_id="tenant-b", regions=(region(),),
        )
    assert not port.calls


@pytest.mark.parametrize("field,value", [
    ("tenant_id", "tenant-b"), ("document_id", "doc-b"),
    ("block_id", "another"), ("asset_ref", "asset-other"),
    ("page_number", 2), ("bounding_box", None),
    ("kind", EvidenceKind.IMAGE),
])
def test_provenance_mismatch_is_rejected(field, value):
    port = StubPort(lambda result: replace(result, **{field: value}))
    with pytest.raises(PermissionError):
        VisualEvidenceExtractor(port).enrich(
            document(), tenant_id="tenant-a", regions=(region(),),
        )


@pytest.mark.parametrize("value", ["", "  ", "x" * 21])
def test_empty_or_oversized_output_refused(value):
    port = StubPort(lambda result: replace(result, text=value))
    with pytest.raises(ValueError):
        VisualEvidenceExtractor(port, max_chars_per_region=20).enrich(
            document(), tenant_id="tenant-a", regions=(region(),),
        )


@pytest.mark.parametrize("asset", ["https://bad.example/image", "/etc/passwd", " "])
def test_external_asset_references_refused(asset):
    with pytest.raises(ValueError):
        replace(region(), asset_ref=asset)


def test_duplicate_block_is_rejected_before_model_call():
    port = StubPort()
    with pytest.raises(ValueError):
        VisualEvidenceExtractor(port).enrich(
            document(), tenant_id="tenant-a",
            regions=(replace(region(), block_id="p1-text"),),
        )
    assert not port.calls


def test_invalid_regions_and_limits():
    with pytest.raises(ValueError):
        VisualRegion("x", "asset", EvidenceKind.AUDIO, 1)
    with pytest.raises(ValueError):
        VisualEvidenceExtractor(StubPort(), max_regions=0)
    with pytest.raises(ValueError):
        VisualEvidenceExtractor(StubPort()).enrich(
            document(), tenant_id="tenant-a", regions=(),
        )
