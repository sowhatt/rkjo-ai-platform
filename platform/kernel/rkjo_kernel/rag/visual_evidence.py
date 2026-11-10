"""MM-RAG-04.1: opt-in, tenant-bound visual evidence adapter.

The caller resolves and authorizes opaque assets BEFORE invoking the port.
This module never fetches a URL, renders a PDF, or calls an LLM itself.
A provider response is untrusted until provenance and bounds are checked.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from rkjo_kernel.rag.multimodal_evidence import (
    EvidenceBlock, EvidenceDocument, EvidenceKind, EvidenceLocation,
    ExtractionMethod,
)
from rkjo_kernel.rag.normalization import normalize_text


@dataclass(frozen=True, slots=True)
class VisualRegion:
    block_id: str
    asset_ref: str
    kind: EvidenceKind
    page_number: int
    bounding_box: tuple[float, float, float, float] | None = None

    def __post_init__(self) -> None:
        if self.kind not in (EvidenceKind.IMAGE, EvidenceKind.TABLE):
            raise ValueError("Only image and table regions are supported.")
        # Reuse canonical block validation (opaque asset, geometry, id).
        EvidenceBlock(
            block_id=self.block_id, kind=self.kind, text="",
            extraction_method=ExtractionMethod.VLM,
            location=EvidenceLocation(
                page_number=self.page_number, bounding_box=self.bounding_box
            ),
            asset_ref=self.asset_ref,
        )


@dataclass(frozen=True, slots=True)
class VisualResult:
    tenant_id: str
    document_id: str
    block_id: str
    asset_ref: str
    kind: EvidenceKind
    page_number: int
    bounding_box: tuple[float, float, float, float] | None
    text: str
    confidence: float | None = None


class VisualAnalysisPort(Protocol):
    """Must obtain image bytes through a separately authorized asset resolver.

    The port must not trust free-form URLs or tenant IDs from end users.
    It returns observed descriptions/transcriptions, never invented cell values.
    """
    def analyze(
        self, *, tenant_id: str, document_id: str, region: VisualRegion,
    ) -> VisualResult: ...


class VisualEvidenceExtractor:
    """Append evidence to an existing document without changing OCR text.

    Fail closed: zero or incomplete regions, mismatched provenance, blank
    outputs and duplicate block IDs abort the entire extraction.
    No persistence/indexing is performed.
    """

    def __init__(
        self, port: VisualAnalysisPort, *, max_regions: int = 50,
        max_chars_per_region: int = 20_000,
    ) -> None:
        if not 1 <= max_regions <= 1000 or not 1 <= max_chars_per_region <= 100_000:
            raise ValueError("Invalid visual extraction limits.")
        self.port = port
        self.max_regions = max_regions
        self.max_chars_per_region = max_chars_per_region

    def enrich(
        self, document: EvidenceDocument, *, tenant_id: str,
        regions: tuple[VisualRegion, ...],
    ) -> EvidenceDocument:
        if not tenant_id.strip() or tenant_id != document.tenant_id:
            raise PermissionError("Visual evidence tenant mismatch.")
        if not regions or len(regions) > self.max_regions:
            raise ValueError("Visual region count is invalid.")
        existing = {block.block_id for block in document.blocks}
        generated: list[EvidenceBlock] = []
        for region in regions:
            if region.block_id in existing:
                raise ValueError("Duplicate visual evidence block.")
            existing.add(region.block_id)
            result = self.port.analyze(
                tenant_id=tenant_id, document_id=document.document_id,
                region=region,
            )
            if not isinstance(result, VisualResult) or (
                result.tenant_id != tenant_id
                or result.document_id != document.document_id
                or result.block_id != region.block_id
                or result.asset_ref != region.asset_ref
                or result.kind != region.kind
                or result.page_number != region.page_number
                or result.bounding_box != region.bounding_box
            ):
                raise PermissionError("Visual result provenance mismatch.")
            content = normalize_text(result.text)
            if not content or len(content) > self.max_chars_per_region:
                raise ValueError("Empty or oversized visual analysis.")
            generated.append(EvidenceBlock(
                block_id=region.block_id, kind=region.kind, text=content,
                extraction_method=ExtractionMethod.VLM,
                location=EvidenceLocation(
                    page_number=region.page_number,
                    bounding_box=region.bounding_box,
                ),
                asset_ref=region.asset_ref, confidence=result.confidence,
            ))
        return EvidenceDocument(
            tenant_id=document.tenant_id, document_id=document.document_id,
            source_type=document.source_type,
            blocks=(*document.blocks, *generated),
            extraction_version=document.extraction_version + "+visual-v1",
        )
