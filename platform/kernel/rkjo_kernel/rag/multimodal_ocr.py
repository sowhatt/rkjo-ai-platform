"""MM-RAG-02: fail-closed mixed PDF extraction using a pluggable OCR port.

No concrete OCR backend or PDF rendering is bundled. An adapter must enforce
transport security, tenant authorization and page binding before returning text.
Nothing is persisted or indexed by this extraction stage.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pypdf import PdfReader

from rkjo_kernel.rag.multimodal_evidence import (
    EvidenceBlock, EvidenceDocument, EvidenceKind, EvidenceLocation, ExtractionMethod,
)
from rkjo_kernel.rag.normalization import normalize_text


@dataclass(frozen=True, slots=True)
class OCRPageResult:
    tenant_id: str
    document_id: str
    page_number: int
    text: str
    confidence: float | None = None

    def __post_init__(self) -> None:
        if not self.tenant_id.strip() or not self.document_id.strip():
            raise ValueError("OCR tenant and document required.")
        if self.page_number < 1:
            raise ValueError("OCR page must be positive.")
        if self.confidence is not None and (
            isinstance(self.confidence, bool) or not isinstance(self.confidence, (float, int))
            or not 0 <= self.confidence <= 1
        ):
            raise ValueError("Invalid OCR confidence.")


class PDFPageOCRPort(Protocol):
    """OCR implementation provides text for one page from an authorized PDF.

    Implementations should rasterize only the requested page, enforce quotas,
    handle sensitive data appropriately and return the supplied identifiers.
    """
    def recognize_page(self, *, pdf_path: Path, tenant_id: str,
                       document_id: str, page_number: int) -> OCRPageResult: ...


@dataclass(frozen=True, slots=True)
class MixedPDFExtraction:
    document: EvidenceDocument
    page_count: int
    ocr_pages: tuple[int, ...]
    rejected_pages: tuple[int, ...]

    @property
    def complete(self) -> bool:
        return not self.rejected_pages


class MixedPDFEvidenceExtractor:
    """Use native text where present; OCR only pages with no native text.

    An empty/unreadable OCR result is fatal by default; optional incomplete
    output is marked explicitly and must not be indexed without review.
    """
    def __init__(self, ocr: PDFPageOCRPort, *, max_pages: int = 100,
                 max_chars_per_page: int = 100_000) -> None:
        if not 1 <= max_pages <= 10_000 or not 1 <= max_chars_per_page <= 1_000_000:
            raise ValueError("Invalid extraction limits.")
        self.ocr = ocr
        self.max_pages = max_pages
        self.max_chars_per_page = max_chars_per_page

    def extract(self, path: str | Path, *, tenant_id: str,
                document_id: str, allow_incomplete: bool = False) -> MixedPDFExtraction:
        source = Path(path)
        if source.suffix.lower() != ".pdf" or not source.is_file():
            raise ValueError("Expected an existing PDF file.")
        if not tenant_id.strip() or not document_id.strip():
            raise ValueError("Explicit tenant and document required.")
        reader = PdfReader(str(source))
        count = len(reader.pages)
        if not 1 <= count <= self.max_pages:
            raise ValueError("PDF page limit exceeded or document empty.")

        blocks: list[EvidenceBlock] = []
        ocr_pages: list[int] = []
        rejected: list[int] = []
        for number, page in enumerate(reader.pages, start=1):
            native = normalize_text(page.extract_text() or "")
            if len(native) > self.max_chars_per_page:
                raise ValueError("Page text size limit exceeded.")
            if native:
                blocks.append(EvidenceBlock(
                    block_id=f"p{number}-text", kind=EvidenceKind.TEXT,
                    text=native, extraction_method=ExtractionMethod.NATIVE_TEXT,
                    location=EvidenceLocation(page_number=number),
                ))
                continue
            result = self.ocr.recognize_page(
                pdf_path=source, tenant_id=tenant_id,
                document_id=document_id, page_number=number,
            )
            if (not isinstance(result, OCRPageResult) or
                result.tenant_id != tenant_id or
                result.document_id != document_id or
                result.page_number != number):
                raise PermissionError("OCR result provenance mismatch.")
            text = normalize_text(result.text)
            if len(text) > self.max_chars_per_page:
                raise ValueError("OCR page text size limit exceeded.")
            if not text:
                rejected.append(number)
                if not allow_incomplete:
                    raise ValueError("Unusable OCR page; incomplete evidence refused.")
                continue
            ocr_pages.append(number)
            blocks.append(EvidenceBlock(
                block_id=f"p{number}-ocr", kind=EvidenceKind.TEXT,
                text=text, extraction_method=ExtractionMethod.OCR,
                location=EvidenceLocation(page_number=number),
                confidence=result.confidence,
            ))
        if not blocks:
            raise ValueError("No extractable evidence.")
        return MixedPDFExtraction(
            document=EvidenceDocument(
                tenant_id=tenant_id, document_id=document_id, source_type="pdf",
                blocks=tuple(blocks), extraction_version="mixed-native-ocr-v1",
            ),
            page_count=count, ocr_pages=tuple(ocr_pages),
            rejected_pages=tuple(rejected),
        )
