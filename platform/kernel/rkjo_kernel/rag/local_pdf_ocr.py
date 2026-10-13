"""Local, optional OCR adapter for MM-RAG-02.2.

Requires external Poppler (pdftoppm) and Tesseract binaries. No shell execution,
no remote OCR API and no PDF/image bytes in exception messages.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from rkjo_kernel.rag.multimodal_ocr import OCRPageResult


class LocalTesseractPDFOCR:
    """Render exactly one PDF page then OCR it inside a private temp directory.

    Caller must already authenticate tenant/document access to the PDF. This
    adapter has no storage access control of its own; never expose it directly
    as an unauthenticated service.
    """

    def __init__(
        self, *, language: str = "fra+eng", timeout_seconds: int = 30,
        max_pdf_bytes: int = 20 * 1024 * 1024,
        max_output_chars: int = 100_000,
        max_image_bytes: int = 20 * 1024 * 1024,
        max_dimension: int = 1800,
        renderer_binary: str = "pdftoppm",
        ocr_binary: str = "tesseract",
    ) -> None:
        if not language or not all(
            part.isascii() and part.replace("_", "").isalnum()
            for part in language.split("+")
        ):
            raise ValueError("Invalid OCR language identifier.")
        if not 1 <= timeout_seconds <= 300:
            raise ValueError("Invalid OCR timeout.")
        if not 1 <= max_pdf_bytes <= 200 * 1024 * 1024:
            raise ValueError("Invalid PDF byte limit.")
        if not 1 <= max_output_chars <= 1_000_000:
            raise ValueError("Invalid OCR output limit.")
        if not 1 <= max_image_bytes <= 200 * 1024 * 1024:
            raise ValueError("Invalid rendered image limit.")
        if not 100 <= max_dimension <= 4096:
            raise ValueError("Invalid render dimension.")
        # Only command names or absolute paths; no shell, PATH segments or args.
        for binary in (renderer_binary, ocr_binary):
            path = Path(binary)
            if not binary or (not path.is_absolute() and path.name != binary):
                raise ValueError("Binary must be a command name or absolute path.")
        self.language = language
        self.timeout_seconds = timeout_seconds
        self.max_pdf_bytes = max_pdf_bytes
        self.max_output_chars = max_output_chars
        self.max_image_bytes = max_image_bytes
        self.max_dimension = max_dimension
        self.renderer_binary = renderer_binary
        self.ocr_binary = ocr_binary

    def recognize_page(
        self, *, pdf_path: Path, tenant_id: str,
        document_id: str, page_number: int,
    ) -> OCRPageResult:
        if not tenant_id.strip() or not document_id.strip() or page_number < 1:
            raise ValueError("Explicit OCR provenance required.")
        source = Path(pdf_path)
        if source.suffix.lower() != ".pdf" or not source.is_file():
            raise ValueError("OCR requires an existing PDF.")
        if source.stat().st_size > self.max_pdf_bytes:
            raise ValueError("OCR PDF byte limit exceeded.")

        renderer = shutil.which(self.renderer_binary)
        ocr = shutil.which(self.ocr_binary)
        if not renderer or not ocr:
            raise RuntimeError("Local OCR dependencies missing: pdftoppm/tesseract.")

        try:
            with TemporaryDirectory(prefix="rkjo-ocr-") as directory:
                prefix = Path(directory) / "page"
                render_args = [
                    renderer, "-f", str(page_number), "-l", str(page_number),
                    "-singlefile", "-scale-to", str(self.max_dimension),
                    "-png", str(source), str(prefix),
                ]
                self._execute(render_args)
                image = prefix.with_suffix(".png")
                if not image.is_file():
                    raise RuntimeError("PDF page render did not produce an image.")
                if image.stat().st_size > self.max_image_bytes:
                    raise ValueError("Rendered OCR page exceeds byte limit.")

                # Tesseract writes to file; avoid unbounded stdout capture.
                output_prefix = Path(directory) / "recognized"
                self._execute([
                    ocr, str(image), str(output_prefix), "-l", self.language,
                ])
                output_file = output_prefix.with_suffix(".txt")
                if not output_file.is_file():
                    raise RuntimeError("OCR produced no text file.")
                if output_file.stat().st_size > self.max_output_chars * 4:
                    raise ValueError("OCR text output byte limit exceeded.")
                text = output_file.read_text(encoding="utf-8")
                if len(text) > self.max_output_chars:
                    raise ValueError("OCR text output character limit exceeded.")
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Local OCR timed out.") from None
        except subprocess.CalledProcessError:
            raise RuntimeError("Local OCR process failed.") from None

        return OCRPageResult(
            tenant_id=tenant_id, document_id=document_id,
            page_number=page_number, text=text, confidence=None,
        )

    def _execute(self, args: list[str]) -> None:
        # Silence raw tool output: scanned text and PDF internals may be private.
        subprocess.run(
            args, check=True, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=self.timeout_seconds,
        )
