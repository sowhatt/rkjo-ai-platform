import pytest

from rkjo_api.dependencies import (
    get_rag_search_service,
)
from rkjo_api.main import app
from rkjo_kernel.rag.semantic_search import (
    SemanticSearchResponse,
    SemanticSearchResult,
)


class FakeSearchService:

    def __init__(self):
        self.calls = []

    def search(
        self,
        query,
        *,
        limit=5,
        filters=None,
    ):
        self.calls.append(
            (
                query,
                limit,
                filters,
            )
        )

        return SemanticSearchResponse(
            sanitized_query=query,
            result_count=1,
            results=[
                SemanticSearchResult(
                    chunk_id="chunk-001",
                    document_id="doc-001",
                    content=(
                        "Le déficit pluviométrique "
                        "affecte le rendement du maïs."
                    ),
                    score=0.91,
                    metadata={
                        "country": "benin",
                        "domain": "agriculture",
                    },
                )
            ],
        )


@pytest.fixture
def viewer_headers():
    return {
        "X-API-Key": (
            "rkjo-viewer-key"
        )
    }


def install_override(
    service,
):
    app.dependency_overrides[
        get_rag_search_service
    ] = lambda: service


def clear_override():
    app.dependency_overrides.pop(
        get_rag_search_service,
        None,
    )


def test_search_requires_authentication(
    client,
):
    response = client.post(
        "/rag/search",
        json={
            "query": "rendement maïs"
        },
    )

    assert response.status_code == 401


def test_viewer_can_search(
    client,
    viewer_headers,
):
    service = FakeSearchService()

    install_override(service)

    try:
        response = client.post(
            "/rag/search",
            headers=viewer_headers,
            json={
                "query": (
                    "Quels facteurs affectent "
                    "le rendement du maïs ?"
                ),
                "limit": 3,
            },
        )

    finally:
        clear_override()

    assert response.status_code == 200

    payload = response.json()

    assert payload[
        "result_count"
    ] == 1

    assert (
        payload["results"][0][
            "document_id"
        ]
        == "doc-001"
    )

    assert (
        service.calls[0][1]
        == 3
    )


def test_operator_can_search(
    client,
):
    service = FakeSearchService()

    install_override(service)

    try:
        response = client.post(
            "/rag/search",
            headers={
                "X-API-Key": (
                    "rkjo-operator-key"
                )
            },
            json={
                "query": "maïs"
            },
        )

    finally:
        clear_override()

    assert response.status_code == 200


def test_search_limit_above_20_is_rejected(
    client,
    viewer_headers,
):
    response = client.post(
        "/rag/search",
        headers=viewer_headers,
        json={
            "query": "maïs",
            "limit": 21,
        },
    )

    assert response.status_code == 422


def test_empty_query_is_rejected(
    client,
    viewer_headers,
):
    response = client.post(
        "/rag/search",
        headers=viewer_headers,
        json={
            "query": ""
        },
    )

    assert response.status_code == 422
