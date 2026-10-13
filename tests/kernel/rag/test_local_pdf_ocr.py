"""MM-RAG-02.2 unit tests: no real OCR installation needed."""
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from rkjo_kernel.rag.local_pdf_ocr import LocalTesseractPDFOCR
from rkjo_kernel.rag.multimodal_ocr import MixedPDFEvidenceExtractor


@pytest.fixture
def sample(tmp_path):
    path = tmp_path / "sample.pdf"
    path.write_bytes(b"%PDF-fixture")
    return path


def patch_binaries(monkeypatch):
    import rkjo_kernel.rag.local_pdf_ocr as module
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/" + name)


def test_local_ocr_renders_single_page_and_cleans_temp(monkeypatch, sample):
    import rkjo_kernel.rag.local_pdf_ocr as module
    patch_binaries(monkeypatch)
    commands = []

    def fake_run(args, **kwargs):
        assert kwargs["check"]
        assert kwargs["timeout"] == 30
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["stdout"] == subprocess.DEVNULL
        assert kwargs["stderr"] == subprocess.DEVNULL
        commands.append(args)
        if "pdftoppm" in args[0]:
            Path(args[-1] + ".png").write_bytes(b"png")
        else:
            Path(args[2] + ".txt").write_text("Garantie optique 250 EUR", encoding="utf-8")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    result = LocalTesseractPDFOCR().recognize_page(
        pdf_path=sample, tenant_id="a", document_id="doc", page_number=3,
    )
    assert result.text == "Garantie optique 250 EUR"
    assert result.confidence is None
    assert commands[0][commands[0].index("-f") + 1] == "3"
    assert commands[0][commands[0].index("-l") + 1] == "3"
    assert "-scale-to" in commands[0]
    assert commands[1][-2:] == ["-l", "fra+eng"]
    assert not Path(commands[0][-1]).parent.exists()


def test_missing_dependency_rejected(monkeypatch, sample):
    import rkjo_kernel.rag.local_pdf_ocr as module
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="dependencies missing"):
        LocalTesseractPDFOCR().recognize_page(
            pdf_path=sample, tenant_id="a", document_id="doc", page_number=1,
        )


def test_pdf_file_limit_fails_before_tools(monkeypatch, sample):
    import rkjo_kernel.rag.local_pdf_ocr as module
    monkeypatch.setattr(module.shutil, "which",
                        lambda name: pytest.fail("binary should not be resolved"))
    with pytest.raises(ValueError, match="byte limit"):
        LocalTesseractPDFOCR(max_pdf_bytes=1).recognize_page(
            pdf_path=sample, tenant_id="a", document_id="doc", page_number=1,
        )


def test_tesseract_output_size_limit(monkeypatch, sample):
    import rkjo_kernel.rag.local_pdf_ocr as module
    patch_binaries(monkeypatch)

    def fake_run(args, **kwargs):
        if "pdftoppm" in args[0]:
            Path(args[-1] + ".png").write_bytes(b"png")
        else:
            Path(args[2] + ".txt").write_text("excessive", encoding="utf-8")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    with pytest.raises(ValueError, match="character limit"):
        LocalTesseractPDFOCR(max_output_chars=4).recognize_page(
            pdf_path=sample, tenant_id="a", document_id="doc", page_number=1,
        )


def test_render_image_limit(monkeypatch, sample):
    import rkjo_kernel.rag.local_pdf_ocr as module
    patch_binaries(monkeypatch)
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        Path(args[-1] + ".png").write_bytes(b"oversized")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    with pytest.raises(ValueError, match="image exceeds byte limit"):
        LocalTesseractPDFOCR(max_image_bytes=1).recognize_page(
            pdf_path=sample, tenant_id="a", document_id="doc", page_number=1,
        )
    assert len(calls) == 1


def test_timeout_error_does_not_leak_document(monkeypatch, sample):
    import rkjo_kernel.rag.local_pdf_ocr as module
    patch_binaries(monkeypatch)

    def fake_run(args, **kwargs):
        raise subprocess.TimeoutExpired(args, 30)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="Local OCR timed out") as err:
        LocalTesseractPDFOCR().recognize_page(
            pdf_path=sample, tenant_id="a", document_id="doc", page_number=1,
        )
    assert "sample.pdf" not in str(err.value)


def test_mixed_extractor_with_local_provider(monkeypatch, sample):
    import rkjo_kernel.rag.local_pdf_ocr as local
    import rkjo_kernel.rag.multimodal_ocr as mixed
    patch_binaries(monkeypatch)
    monkeypatch.setattr(
        mixed, "PdfReader",
        lambda path: SimpleNamespace(pages=[
            SimpleNamespace(extract_text=lambda: "Native guarantee"),
            SimpleNamespace(extract_text=lambda: ""),
        ]),
    )

    def fake_run(args, **kwargs):
        if "pdftoppm" in args[0]:
            Path(args[-1] + ".png").write_bytes(b"png")
        else:
            Path(args[2] + ".txt").write_text("OCR guarantee", encoding="utf-8")

    monkeypatch.setattr(local.subprocess, "run", fake_run)
    result = MixedPDFEvidenceExtractor(LocalTesseractPDFOCR()).extract(
        sample, tenant_id="a", document_id="doc",
    )
    assert result.complete
    assert result.ocr_pages == (2,)
    assert [b.text for b in result.document.blocks] == ["Native guarantee", "OCR guarantee"]


@pytest.mark.parametrize("language", ["fra;rm -rf", "", "../fra", "fra+"])
def test_reject_invalid_language(language):
    with pytest.raises(ValueError):
        LocalTesseractPDFOCR(language=language)
