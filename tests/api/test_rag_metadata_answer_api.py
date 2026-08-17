from rkjo_api.dependencies import (
    get_rag_answering_service,
)
from rkjo_api.main import app
from rkjo_kernel.rag.generation_models import (
    RAGAnswer,
)


class RecordingAnswerService:
    def __init__(self):
        self.calls = []

    def answer(
        self,
        question,
        *,
        limit=5,
        filters=None,
    ):
        self.calls.append(
            (
                question,
                limit,
                filters,
            )
        )

        return RAGAnswer(
            answer="Réponse",
            sanitized_query=question,
            sources=[],
        )


def test_answer_api_propagates_filters(
    client,
    viewer_headers,
):
    service = RecordingAnswerService()

    app.dependency_overrides[
        get_rag_answering_service
    ] = lambda: service

    try:
        response = client.post(
            "/rag/answer",
            headers=viewer_headers,
            json={
                "question": "Question",
                "filters": {
                    "country": "benin",
                    "domain": "agriculture",
                    "year": 2026,
                },
            },
        )
    finally:
        app.dependency_overrides.pop(
            get_rag_answering_service,
            None,
        )

    assert response.status_code == 200

    _, _, filters = service.calls[0]

    assert filters.metadata == {
        "country": "benin",
        "domain": "agriculture",
        "year": 2026,
    }


def test_answer_api_rejects_unknown_filter(
    client,
    viewer_headers,
):
    response = client.post(
        "/rag/answer",
        headers=viewer_headers,
        json={
            "question": "Question",
            "filters": {
                "private": "value"
            },
        },
    )

    assert response.status_code == 422


def test_answer_api_rejects_invalid_year(
    client,
    viewer_headers,
):
    response = client.post(
        "/rag/answer",
        headers=viewer_headers,
        json={
            "question": "Question",
            "filters": {
                "year": 1200
            },
        },
    )

    assert response.status_code == 422
