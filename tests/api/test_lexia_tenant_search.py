"""Strict LexIA RAG endpoint: unbound credentials and cross-tenant leakage blocked."""
from rkjo_api.dependencies import get_rag_search_service
from rkjo_api.main import app
from rkjo_kernel.rag.semantic_search import SemanticSearchResponse, SemanticSearchResult


class FakeSearch:
    def __init__(self, returned_tenant="tenant-a"):
        self.returned_tenant = returned_tenant
        self.calls = []

    def search(self, query, *, limit=5, filters=None):
        self.calls.append(filters)
        return SemanticSearchResponse(
            sanitized_query=query,
            result_count=1,
            results=[
                SemanticSearchResult(
                    chunk_id="chunk-1", document_id="doc-1",
                    content="legal example", score=0.8,
                    metadata={
                        "tenant_id": self.returned_tenant,
                        "domain": "droit", "country": "BJ",
                    },
                ),
            ],
        )


def test_lexia_search_binds_authenticated_tenant(client, viewer_headers):
    service = FakeSearch()
    app.dependency_overrides[get_rag_search_service] = lambda: service
    try:
        response = client.post(
            "/rag/lexia/search", headers=viewer_headers,
            json={"query": "Article", "filters": {"domain": "droit", "country": "BJ"}},
        )
    finally:
        app.dependency_overrides.pop(get_rag_search_service, None)
    assert response.status_code == 200
    assert service.calls[0].metadata["tenant_id"] == "tenant-a"


def test_lexia_search_rejects_unbound_credential(client, viewer_headers, monkeypatch):
    monkeypatch.delenv("RKJO_VIEWER_TENANT_ID", raising=False)
    service = FakeSearch()
    app.dependency_overrides[get_rag_search_service] = lambda: service
    try:
        response = client.post(
            "/rag/lexia/search", headers=viewer_headers,
            json={"query": "Article", "filters": {"tenant_id": "tenant-a"}},
        )
    finally:
        app.dependency_overrides.pop(get_rag_search_service, None)
    assert response.status_code == 403
    assert service.calls == []


def test_lexia_search_rejects_cross_tenant_filter(client, viewer_headers):
    service = FakeSearch()
    app.dependency_overrides[get_rag_search_service] = lambda: service
    try:
        response = client.post(
            "/rag/lexia/search", headers=viewer_headers,
            json={"query": "Article", "filters": {"tenant_id": "tenant-b"}},
        )
    finally:
        app.dependency_overrides.pop(get_rag_search_service, None)
    assert response.status_code == 403
    assert service.calls == []


def test_lexia_search_rejects_foreign_result(client, viewer_headers):
    service = FakeSearch(returned_tenant="tenant-b")
    app.dependency_overrides[get_rag_search_service] = lambda: service
    try:
        response = client.post(
            "/rag/lexia/search", headers=viewer_headers,
            json={"query": "Article"},
        )
    finally:
        app.dependency_overrides.pop(get_rag_search_service, None)
    assert response.status_code == 502


def test_lexia_search_rejects_unscoped_result(client, viewer_headers):
    service = FakeSearch(returned_tenant=None)
    app.dependency_overrides[get_rag_search_service] = lambda: service
    try:
        response = client.post(
            "/rag/lexia/search", headers=viewer_headers,
            json={"query": "Article"},
        )
    finally:
        app.dependency_overrides.pop(get_rag_search_service, None)
    assert response.status_code == 502
