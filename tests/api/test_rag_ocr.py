"""MM-RAG-02.5 API security and compatibility tests."""
from rkjo_api.main import app
from rkjo_api.rag_ocr import get_ocr_ingestion_service, OCRUploadResult


class FakeOCRService:
    def __init__(self):
        self.calls = []

    def ingest(self, path, *, tenant_id, document_id):
        assert path.exists()
        self.calls.append((tenant_id, document_id))
        return OCRUploadResult(
            document_id=document_id, page_count=1, ocr_pages=[1],
            chunk_count=2, content_hash="a" * 64,
        )


def upload(client, headers=None, filename="test.pdf", contents=b"%PDF-1.4 fake"):
    return client.post(
        "/rag/ocr/documents", headers=headers or {},
        files={"file": (filename, contents, "application/pdf")},
        data={"document_id": "contract-01"},
    )


def test_ocr_disabled_by_default(client, monkeypatch):
    monkeypatch.delenv("RKJO_RAG_OCR_API_ENABLED", raising=False)
    response = upload(client, {"X-API-Key": "rkjo-operator-key"})
    assert response.status_code == 404


def test_ocr_rejects_unauthenticated(client, monkeypatch):
    monkeypatch.setenv("RKJO_RAG_OCR_API_ENABLED", "true")
    assert upload(client).status_code == 401


def test_ocr_requires_operator(client, monkeypatch):
    monkeypatch.setenv("RKJO_RAG_OCR_API_ENABLED", "true")
    assert upload(client, {"X-API-Key": "rkjo-viewer-key"}).status_code == 403


def test_ocr_accepts_operator_bound_to_tenant(client, monkeypatch):
    monkeypatch.setenv("RKJO_RAG_OCR_API_ENABLED", "true")
    service = FakeOCRService()
    app.dependency_overrides[get_ocr_ingestion_service] = lambda: service
    try:
        response = upload(client, {"X-API-Key": "rkjo-operator-key"})
    finally:
        app.dependency_overrides.pop(get_ocr_ingestion_service, None)
    assert response.status_code == 201, response.text
    assert response.json()["ocr_pages"] == [1]
    assert service.calls == [("tenant-a", "contract-01")]


def test_ocr_rejects_non_pdf(client, monkeypatch):
    monkeypatch.setenv("RKJO_RAG_OCR_API_ENABLED", "true")
    response = upload(client, {"X-API-Key": "rkjo-operator-key"}, filename="test.txt")
    assert response.status_code == 415


def test_ocr_rejects_invalid_pdf_signature(client, monkeypatch):
    monkeypatch.setenv("RKJO_RAG_OCR_API_ENABLED", "true")
    response = upload(client, {"X-API-Key": "rkjo-operator-key"}, contents=b"not-a-pdf")
    assert response.status_code == 422
