from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pypdf import PdfReader

from rkjo_kernel.rag.ingestion_models import LoadedDocument
from rkjo_kernel.rag.normalization import normalize_text


class DocumentLoader(ABC):

    @abstractmethod
    def supports(self, path: Path) -> bool:
        raise NotImplementedError

    @abstractmethod
    def load(self, path: Path) -> LoadedDocument:
        raise NotImplementedError


class PlainTextDocumentLoader(DocumentLoader):

    SUPPORTED_SUFFIXES = {
        ".txt",
        ".md",
        ".markdown",
    }

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self.SUPPORTED_SUFFIXES

    def load(self, path: Path) -> LoadedDocument:
        if not path.exists():
            raise FileNotFoundError(path)

        if not path.is_file():
            raise ValueError(
                "Document path must reference a file."
            )

        content = normalize_text(
            path.read_text(encoding="utf-8")
        )

        if not content:
            raise ValueError(
                "Text document contains no usable content."
            )

        return LoadedDocument(
            content=content,
            source_path=path,
            source_type=path.suffix.lower().lstrip("."),
            metadata={
                "filename": path.name,
                "suffix": path.suffix.lower(),
            },
        )


class PdfDocumentLoader(DocumentLoader):

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() == ".pdf"

    def load(self, path: Path) -> LoadedDocument:
        if not path.exists():
            raise FileNotFoundError(path)

        reader = PdfReader(str(path))

        pages = []

        for page in reader.pages:
            text = page.extract_text()

            if text:
                normalized = normalize_text(text)

                if normalized:
                    pages.append(normalized)

        content = normalize_text(
            "\n\n".join(pages)
        )

        if not content:
            raise ValueError(
                "PDF contains no extractable text."
            )

        return LoadedDocument(
            content=content,
            source_path=path,
            source_type="pdf",
            metadata={
                "filename": path.name,
                "suffix": ".pdf",
                "page_count": len(reader.pages),
            },
        )


class CompositeDocumentLoader:

    def __init__(self) -> None:
        self.loaders = [
            PdfDocumentLoader(),
            PlainTextDocumentLoader(),
        ]

    def load(
        self,
        path: str | Path,
    ) -> LoadedDocument:
        source = Path(path)

        for loader in self.loaders:
            if loader.supports(source):
                return loader.load(source)

        raise ValueError(
            f"Unsupported document format: {source.suffix or '<none>'}"
        )
