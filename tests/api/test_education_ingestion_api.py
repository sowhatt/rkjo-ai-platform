from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rkjo_api.education_ingestion import router


def test_analyze_corrected_copy_returns_per_question_alignment(monkeypatch):
    tenant_id = uuid4()
    learner_id = uuid4()

    from rkjo_api import education_ingestion
    monkeypatch.setattr(education_ingestion, "require_uuid_tenant", lambda request: tenant_id)

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/education/documents/analyze",
        json={
            "learner_id": str(learner_id),
            "filename": "copie.pdf",
            "media_type": "application/pdf",
            "extracted_text": "Question 1: cellule et membrane. 2/2\nQuestion 2: membrane. 0/2",
            "kind": "corrected_copy",
            "referential": [{
                "code": "MED.BIO.CELL",
                "label": "Biologie cellulaire",
                "keywords": ["cellule", "membrane"],
                "importance": 3,
            }],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "corrected_copy"
    assert payload["provenance"] == "learner_upload"
    assert len(payload["questions"]) == 2
    assert payload["questions"][0]["competency_code"] == "MED.BIO.CELL"
    assert payload["questions"][0]["requires_confirmation"] is False
    assert payload["questions"][1]["requires_confirmation"] is True
    assert payload["questions"][1]["earned_points"] == 0.0
