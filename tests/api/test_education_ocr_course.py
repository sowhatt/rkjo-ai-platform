"""MM-RAG-03.2 course-scoped OCR API security and linking."""
import pytest

from rkjo_api.main import app
from rkjo_api.rag_ocr import get_ocr_ingestion_service, OCRUploadResult
from rkjo_api.dependencies import get_education_course_service


class FakeCourseService:
    def __init__(self, available=True):
        self.available = available
        self.lookups = []
        self.attachments = []

    def get(self, *, tenant_id, course_id):
        self.lookups.append((tenant_id, course_id))
        if not self.available:
            raise LookupError("No course")
        return object()

    def attach_document(self, *, tenant_id, course_id, document_id):
        self.attachments.append((tenant_id, course_id, document_id))
        return object()


class FakeOCRService:
    def __init__(self):
        self.calls = []

    def ingest(self, path, *, tenant_id, document_id):
        assert path.exists()
        self.calls.append((tenant_id, document_id))
        return OCRUploadResult(
            document_id=document_id,
            page_count=1,
            ocr_pages=[1],
            chunk_count=1,
            content_hash="f" * 64,
        )


@pytest.fixture
def services():
    courses = FakeCourseService()
    ocr = FakeOCRService()
    app.dependency_overrides[get_education_course_service] = lambda: courses
    app.dependency_overrides[get_ocr_ingestion_service] = lambda: ocr
    yield courses, ocr
    app.dependency_overrides.pop(get_education_course_service, None)
    app.dependency_overrides.pop(get_ocr_ingestion_service, None)


def upload(client, *, headers=None, filename="course.pdf", content=b"%PDF-1.4\n"):
    return client.post(
        "/rag/ocr/courses/course-01/documents",
        headers=headers or {},
        files={"file": (filename, content, "application/pdf")},
    )


def test_course_ocr_requires_flag(client, services, monkeypatch):
    monkeypatch.delenv("RKJO_RAG_OCR_API_ENABLED", raising=False)
    assert upload(client, headers={"X-API-Key": "rkjo-operator-key"}).status_code == 404
    assert services[1].calls == []


def test_course_ocr_rejects_viewer(client, services, monkeypatch):
    monkeypatch.setenv("RKJO_RAG_OCR_API_ENABLED", "true")
    assert upload(client, headers={"X-API-Key": "rkjo-viewer-key"}).status_code == 403
    assert services[0].lookups == []


def test_course_ocr_requires_bound_tenant(client, services, monkeypatch):
    monkeypatch.setenv("RKJO_RAG_OCR_API_ENABLED", "true")
    monkeypatch.delenv("RKJO_OPERATOR_TENANT_ID", raising=False)
    assert upload(client, headers={"X-API-Key": "rkjo-operator-key"}).status_code == 403
    assert services[0].lookups == []


def test_course_ocr_checks_course_before_processing(client, services, monkeypatch):
    monkeypatch.setenv("RKJO_RAG_OCR_API_ENABLED", "true")
    services[0].available = False
    assert upload(client, headers={"X-API-Key": "rkjo-operator-key"}).status_code == 404
    assert services[1].calls == []


def test_course_ocr_ingests_then_attaches_document(client, services, monkeypatch):
    monkeypatch.setenv("RKJO_RAG_OCR_API_ENABLED", "true")
    response = upload(client, headers={"X-API-Key": "rkjo-operator-key"})
    assert response.status_code == 201, response.text
    doc_id = response.json()["document_id"]
    assert doc_id.startswith("education-")
    assert services[0].lookups == [("tenant-a", "course-01")]
    assert services[1].calls == [("tenant-a", doc_id)]
    assert services[0].attachments == [("tenant-a", "course-01", doc_id)]


def test_course_ocr_rejects_invalid_pdf(client, services, monkeypatch):
    monkeypatch.setenv("RKJO_RAG_OCR_API_ENABLED", "true")
    response = upload(
        client, headers={"X-API-Key": "rkjo-operator-key"}, content=b"not pdf",
    )
    assert response.status_code == 422
    assert services[1].calls == []
    assert services[0].attachments == []
