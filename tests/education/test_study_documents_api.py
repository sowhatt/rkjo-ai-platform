"""Study preview endpoint: identity and content rules without network or storage."""
from io import BytesIO

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from rkjo_api.education_study_documents import router


def app():
    instance = FastAPI()

    @instance.middleware("http")
    async def fake_identity(request, call_next):
        # Middleware simulates only already-authenticated identity for local tests.
        if request.headers.get("authorization") == "Bearer fixture-student":
            request.state.api_subject = "student-1"
            request.state.api_tenant_id = "university-1"
        return await call_next(request)

    instance.include_router(router)
    return TestClient(instance)


def blank_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_denies_missing_individual_identity():
    with app() as client:
        response = client.post(
            "/education/study/preview-pdf",
            data={"programme_id": "medicine", "ue_id": "anatomy"},
            files={"file": ("course.pdf", blank_pdf(), "application/pdf")},
        )
    assert response.status_code == 403


def test_denies_non_pdf_mime():
    with app() as client:
        response = client.post(
            "/education/study/preview-pdf",
            headers={"Authorization": "Bearer fixture-student"},
            data={"programme_id": "medicine", "ue_id": "anatomy"},
            files={"file": ("note.txt", b"hello", "text/plain")},
        )
    assert response.status_code == 415


def test_blank_pdf_requires_ocr():
    with app() as client:
        response = client.post(
            "/education/study/preview-pdf",
            headers={"Authorization": "Bearer fixture-student"},
            data={"programme_id": "medicine", "ue_id": "anatomy", "document_type": "cm"},
            files={"file": ("course.pdf", blank_pdf(), "application/pdf")},
        )
    assert response.status_code == 422
    assert "OCR required" in response.json()["detail"]
