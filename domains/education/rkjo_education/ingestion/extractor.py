"""Text extraction adapters for learner-uploaded education documents."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree

from pypdf import PdfReader


class DocumentExtractionError(ValueError):
    pass


class EducationDocumentExtractor:
    MAX_BYTES = 20 * 1024 * 1024
    TEXT_TYPES = {"text/plain", "text/markdown"}
    PDF_TYPES = {"application/pdf"}
    DOCX_TYPES = {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }

    def extract(self, *, filename: str, media_type: str, content: bytes) -> str:
        if not content:
            raise DocumentExtractionError("Le document est vide.")
        if len(content) > self.MAX_BYTES:
            raise DocumentExtractionError("Le document dépasse la limite de 20 Mo.")

        suffix = Path(filename).suffix.lower()
        if media_type in self.TEXT_TYPES or suffix in {".txt", ".md"}:
            text = content.decode("utf-8", errors="replace")
        elif media_type in self.PDF_TYPES or suffix == ".pdf":
            text = self._pdf(content)
        elif media_type in self.DOCX_TYPES or suffix == ".docx":
            text = self._docx(content)
        elif media_type.startswith("image/") or suffix in {".png", ".jpg", ".jpeg", ".heic"}:
            raise DocumentExtractionError(
                "Cette image nécessite l’OCR/multimodal RKJO, qui n’est pas encore activé."
            )
        else:
            raise DocumentExtractionError("Format de document non pris en charge.")

        normalized = "\n".join(line.rstrip() for line in text.splitlines()).strip()
        if not normalized:
            raise DocumentExtractionError(
                "Aucun texte exploitable n’a été extrait du document."
            )
        return normalized

    @staticmethod
    def _pdf(content: bytes) -> str:
        try:
            reader = PdfReader(BytesIO(content))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as exc:
            raise DocumentExtractionError("Impossible de lire ce PDF.") from exc

    @staticmethod
    def _docx(content: bytes) -> str:
        try:
            with ZipFile(BytesIO(content)) as archive:
                xml = archive.read("word/document.xml")
        except (BadZipFile, KeyError) as exc:
            raise DocumentExtractionError("Impossible de lire ce document Word.") from exc
        root = ElementTree.fromstring(xml)
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs = []
        for paragraph in root.iter(f"{namespace}p"):
            parts = [node.text or "" for node in paragraph.iter(f"{namespace}t")]
            if parts:
                paragraphs.append("".join(parts))
        return "\n".join(paragraphs)
