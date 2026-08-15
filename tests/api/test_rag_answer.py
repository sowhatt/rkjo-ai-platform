import pytest

from rkjo_api.dependencies import (
    get_rag_answering_service,
)
from rkjo_api.main import app
from rkjo_kernel.rag.generation_models import (
    AnswerSource,
    RAGAnswer,
)


class FakeAnsweringService:

    def __init__(self):
        self.calls = []

    def answer(
        self,
        question,
        *,
        limit=5,
    ):
        self.calls.append(
            (question, limit)
        )

        return RAGAnswer(
            answer=(
                "Une sécheresse prolongée peut "
                "réduire le rendement du maïs [1]."
            ),
            sanitized_query=(
                question.replace(
                    "jean@example.com",
                    "[EMAIL]",
                )
            ),
            sources=[
                AnswerSource(
                    citation=1,
                    document_id="openai-rag-002",
                    chunk_id="chunk-001",
                    score=0.91,
                )
            ],
        )


@pytest.fixture
def viewer_headers():
    return {
        "X-API-Key": "rkjo-viewer-key"
    }


def install_override(
    service,
):
    app.dependency_overrides[
        get_rag_answering_service
    ] = lambda: service


def clear_override():
    app.dependency_overrides.pop(
        get_rag_answering_service,
        None,
    )


def test_answer_requires_authentication(
    client,
):
    response = client.post(
        "/rag/answer",
        json={
            "question": (
                "Pourquoi le rendement "
                "du maïs baisse ?"
            )
        },
    )

    assert response.status_code == 401


def test_viewer_can_generate_grounded_answer(
    client,
    viewer_headers,
):
    service = FakeAnsweringService()

    install_override(service)

    try:
        response = client.post(
            "/rag/answer",
            headers=viewer_headers,
            json={
                "question": (
                    "Quels facteurs réduisent "
                    "le rendement du maïs ?"
                ),
                "limit": 3,
            },
        )

    finally:
        clear_override()

    assert response.status_code == 200

    payload = response.json()

    assert "[1]" in payload["answer"]

    assert (
        payload["sources"][0][
            "document_id"
        ]
        == "openai-rag-002"
    )

    assert (
        payload["sources"][0][
            "citation"
        ]
        == 1
    )

    assert service.calls == [
        (
            "Quels facteurs réduisent "
            "le rendement du maïs ?",
            3,
        )
    ]


def test_answer_response_exposes_sanitized_query(
    client,
    viewer_headers,
):
    service = FakeAnsweringService()

    install_override(service)

    try:
        response = client.post(
            "/rag/answer",
            headers=viewer_headers,
            json={
                "question": (
                    "Que dit jean@example.com "
                    "sur le maïs ?"
                )
            },
        )

    finally:
        clear_override()

    assert response.status_code == 200

    assert (
        response.json()[
            "sanitized_query"
        ]
        == "Que dit [EMAIL] sur le maïs ?"
    )


def test_answer_rejects_empty_question(
    client,
    viewer_headers,
):
    response = client.post(
        "/rag/answer",
        headers=viewer_headers,
        json={
            "question": ""
        },
    )

    assert response.status_code == 422


def test_answer_rejects_limit_above_20(
    client,
    viewer_headers,
):
    response = client.post(
        "/rag/answer",
        headers=viewer_headers,
        json={
            "question": "Question",
            "limit": 21,
        },
    )

    assert response.status_code == 422
