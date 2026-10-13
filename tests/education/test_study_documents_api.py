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


def text_pdf():
    """Create a self-contained synthetic course PDF with extractable text."""
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): ref})
    })
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 50 700 Td (Quatre cavites du coeur) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def post_study(client, *, ai=False):
    return client.post(
        "/education/study/preview-pdf",
        headers={"Authorization": "Bearer fixture-student"},
        data={"programme_id": "medicine-year-1", "ue_id": "anatomie",
              "document_type": "cm", "generate_ai": str(ai).lower()},
        files={"file": ("course.pdf", text_pdf(), "application/pdf")},
    )


def test_default_preview_is_local_without_ai(monkeypatch):
    monkeypatch.delenv("RKJO_EDU_STUDY_AI_ENABLED", raising=False)
    with app() as client:
        response = post_study(client)
    assert response.status_code == 200
    assert response.json()["ai_materials"] is None
    assert response.json()["revision_notes"][0]["citation"]["page"] == 1


def test_ai_opt_in_requires_enabled_provider(monkeypatch):
    monkeypatch.delenv("RKJO_EDU_STUDY_AI_ENABLED", raising=False)
    with app() as client:
        response = post_study(client, ai=True)
    assert response.status_code == 503


def test_ai_opt_in_with_simulated_provider(monkeypatch):
    from rkjo_api import education_study_documents as module
    monkeypatch.setenv("RKJO_EDU_STUDY_AI_ENABLED", "enabled")
    monkeypatch.setenv("RKJO_EDU_STUDY_AI_ENDPOINT", "https://example.test/v1/chat/completions")
    monkeypatch.setenv("RKJO_EDU_STUDY_AI_KEY", "placeholder")
    monkeypatch.setenv("RKJO_EDU_STUDY_AI_MODEL", "simulated")

    class SimulatedProvider:
        def __init__(self, config):
            self.config = config

        def generate(self, request):
            return {"items": [{
                "title": "Notions de cours", "body": "Proposition à vérifier.",
                "segment_ids": [request.source_segments[0][0]],
            }]}

    monkeypatch.setattr(module, "HTTPStudyProvider", SimulatedProvider)
    with app() as client:
        response = post_study(client, ai=True)
    assert response.status_code == 200
    assert response.json()["ai_materials"]["revision_note"][0]["pages"] == [1]
    assert response.json()["ai_materials"]["mind_map"][0]["pages"] == [1]


def test_ai_output_with_invalid_reference_is_rejected(monkeypatch):
    from rkjo_api import education_study_documents as module
    monkeypatch.setenv("RKJO_EDU_STUDY_AI_ENABLED", "enabled")
    monkeypatch.setenv("RKJO_EDU_STUDY_AI_ENDPOINT", "https://example.test/v1/chat/completions")
    monkeypatch.setenv("RKJO_EDU_STUDY_AI_KEY", "placeholder")
    monkeypatch.setenv("RKJO_EDU_STUDY_AI_MODEL", "simulated")

    class IncorrectProvider:
        def __init__(self, config):
            pass

        def generate(self, request):
            return {"items": [{
                "title": "Invalide", "body": "Référence non présente.",
                "segment_ids": ["absent-de-la-source"],
            }]}

    monkeypatch.setattr(module, "HTTPStudyProvider", IncorrectProvider)
    with app() as client:
        response = post_study(client, ai=True)
    assert response.status_code == 502
