from rkjo_api.dependencies import (
    get_rag_search_service,
)
from rkjo_api.main import app
from rkjo_kernel.rag.semantic_search import (
    SemanticSearchResponse,
    SemanticSearchResult,
)


class RecordingSearchService:
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
                    chunk_id="agri-1",
                    document_id="meta-agri",
                    content="Agriculture",
                    score=0.9,
                    metadata={
                        "country": "benin",
                        "domain": "agriculture",
                        "tenant_id": "tenant-a",
                    },
                )
            ],
        )


def test_search_api_propagates_filters(
    client,
    viewer_headers,
):
    service = RecordingSearchService()

    app.dependency_overrides[
        get_rag_search_service
    ] = lambda: service

    try:
        response = client.post(
            "/rag/search",
            headers=viewer_headers,
            json={
                "query": "rendement du maïs",
                "limit": 5,
                "filters": {
                    "country": "benin",
                    "domain": "agriculture",
                    "tenant_id": "tenant-a",
                },
            },
        )
    finally:
        app.dependency_overrides.pop(
            get_rag_search_service,
            None,
        )

    assert response.status_code == 200

    _, _, filters = service.calls[0]

    assert filters.metadata == {
        "country": "benin",
        "domain": "agriculture",
        "tenant_id": "tenant-a",
    }


def test_search_api_rejects_unknown_filter(
    client,
    viewer_headers,
):
    response = client.post(
        "/rag/search",
        headers=viewer_headers,
        json={
            "query": "Question",
            "filters": {
                "sql": "DROP TABLE"
            },
        },
    )

    assert response.status_code == 422


def test_search_api_rejects_empty_filter(
    client,
    viewer_headers,
):
    response = client.post(
        "/rag/search",
        headers=viewer_headers,
        json={
            "query": "Question",
            "filters": {
                "domain": "   "
            },
        },
    )

    assert response.status_code == 422
