"""MM-RAG-01: canonical, tenant-scoped evidence extracted from multimodal assets.

This is an extraction contract, not an OCR/VLM implementation. Never index
unverified table cells or invented image descriptions as source evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EvidenceKind(StrEnum):
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


class ExtractionMethod(StrEnum):
    NATIVE_TEXT = "native_text"
    OCR = "ocr"
    VLM = "vlm"
    ASR = "asr"


@dataclass(frozen=True, slots=True)
class EvidenceLocation:
    page_number: int | None = None
    bounding_box: tuple[float, float, float, float] | None = None
    start_ms: int | None = None
    end_ms: int | None = None

    def __post_init__(self) -> None:
        if self.page_number is not None and self.page_number < 1:
            raise ValueError("Page numbers are 1-based.")
        if self.bounding_box is not None:
            coords = self.bounding_box
            if (len(coords) != 4 or any(not 0 <= value <= 1 for value in coords)
                    or coords[2] <= coords[0] or coords[3] <= coords[1]):
                raise ValueError("Bounding boxes must be normalized xyxy coordinates.")
            if self.page_number is None:
                raise ValueError("A page is required for a bounding box.")
        if (self.start_ms is None) != (self.end_ms is None):
            raise ValueError("Both time boundaries are required.")
        if self.start_ms is not None and (
            self.start_ms < 0 or self.end_ms <= self.start_ms
        ):
            raise ValueError("Invalid time segment.")


@dataclass(frozen=True, slots=True)
class EvidenceBlock:
    block_id: str
    kind: EvidenceKind
    text: str
    extraction_method: ExtractionMethod
    location: EvidenceLocation
    asset_ref: str | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.block_id.strip():
            raise ValueError("Block identifier required.")
        if not self.text.strip() and not self.asset_ref:
            raise ValueError("Evidence requires text or an asset reference.")
        if self.confidence is not None and (
            isinstance(self.confidence, bool) or not 0 <= self.confidence <= 1
        ):
            raise ValueError("Confidence must be in [0, 1].")
        if self.asset_ref and (
            not self.asset_ref.strip() or "://" in self.asset_ref or self.asset_ref.startswith("/")
        ):
            raise ValueError("Asset references must be opaque identifiers, not URLs or paths.")
        if self.kind == EvidenceKind.TEXT and not self.text.strip():
            raise ValueError("Text block cannot be empty.")


@dataclass(frozen=True, slots=True)
class EvidenceDocument:
    tenant_id: str
    document_id: str
    source_type: str
    blocks: tuple[EvidenceBlock, ...]
    extraction_version: str = "native-v1"

    def __post_init__(self) -> None:
        if not all([self.tenant_id.strip(), self.document_id.strip(),
                    self.source_type.strip(), self.extraction_version.strip()]):
            raise ValueError("Tenant and document provenance required.")
        identifiers = [block.block_id for block in self.blocks]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Duplicate evidence block identifiers.")

    def searchable_blocks(self) -> tuple[EvidenceBlock, ...]:
        """Only textual evidence is searchable by the current text retriever."""
        return tuple(block for block in self.blocks if block.text.strip())

    def citation(self, block_id: str, *, tenant_id: str) -> dict[str, Any]:
        if tenant_id != self.tenant_id:
            raise PermissionError("Cross-tenant evidence access denied.")
        for block in self.blocks:
            if block.block_id == block_id:
                return {
                    "tenant_id": self.tenant_id,
                    "document_id": self.document_id,
                    "block_id": block.block_id,
                    "kind": block.kind.value,
                    "page_number": block.location.page_number,
                    "bounding_box": block.location.bounding_box,
                    "start_ms": block.location.start_ms,
                    "end_ms": block.location.end_ms,
                    "extraction_method": block.extraction_method.value,
                    "asset_ref": block.asset_ref,
                }
        raise LookupError("Evidence block not found.")
