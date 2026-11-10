"""MM-RAG-01: preserve per-page provenance for native-text PDF files.

Scanned pages without extractable text are explicitly reported as gaps.
No OCR, table cell geometry or vision results are invented.
"""
from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from rkjo_kernel.rag.multimodal_evidence import (
    EvidenceBlock, EvidenceDocument, EvidenceKind, EvidenceLocation,
    ExtractionMethod,
)
from rkjo_kernel.rag.normalization import normalize_text


class NativePDFEvidenceExtractor:
    def extract(self, path: str | Path, *, tenant_id: str,
                document_id: str) -> EvidenceDocument:
        source = Path(path)
        if source.suffix.lower() != ".pdf" or not source.is_file():
            raise ValueError("NativePDFEvidenceExtractor requires a PDF file.")
        if not tenant_id.strip() or not document_id.strip():
            raise ValueError("Explicit tenant and document are required.")
        reader = PdfReader(str(source))
        blocks: list[EvidenceBlock] = []
        empty_pages: list[int] = []
        for page_number, page in enumerate(reader.pages, start=1):
            content = normalize_text(page.extract_text() or "")
            if not content:
                empty_pages.append(page_number)
                continue
            blocks.append(EvidenceBlock(
                block_id=f"p{page_number}-text",
                kind=EvidenceKind.TEXT,
                text=content,
                extraction_method=ExtractionMethod.NATIVE_TEXT,
                location=EvidenceLocation(page_number=page_number),
            ))
        if not blocks:
            raise ValueError(
                "PDF has no native text. OCR processing is required before indexing."
            )
        # Gaps are represented in document-level provenance only; no fake
        # content is injected into embeddings or generated answers.
        return EvidenceDocument(
            tenant_id=tenant_id, document_id=document_id,
            source_type="pdf", blocks=tuple(blocks),
            extraction_version="pypdf-native-v1",
        )

    def inspect(self, path: str | Path, *, tenant_id: str,
                document_id: str) -> dict:
        """Return extraction plus explicit missing-page indices for OCR queue."""
        source = Path(path)
        reader = PdfReader(str(source))
        extracted = self.extract(source, tenant_id=tenant_id,
                                 document_id=document_id)
        pages_with_text = {b.location.page_number for b in extracted.blocks}
        return {
            "document": extracted,
            "total_pages": len(reader.pages),
            "pages_needing_ocr": tuple(
                index for index in range(1, len(reader.pages) + 1)
                if index not in pages_with_text
            ),
        }
