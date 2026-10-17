"""Tenant-bound LexIA search with real JWT validation and HTTP middleware.

Only the retrieval service is mocked; signing, bearer verification, RBAC,
tenant propagation and route-level isolation execute for real.
"""
from rkjo_api.dependencies import get_rag_search_service
from rkjo_api.jwt_auth import create_access_token
from rkjo_api.main import app
from rkjo_api.security import ApiRole
from rkjo_kernel.rag.semantic_search import SemanticSearchResponse, SemanticSearchResult


class RecordingSearch:
    def __init__(self):
        self.calls = []

    def search(self, query, *, limit=5, filters=None):
        self.calls.append(filters)
        tenant = filters.metadata["tenant_id"]
        return SemanticSearchResponse(
            sanitized_query=query,
            result_count=1,
            results=[SemanticSearchResult(
                chunk_id=f"{tenant}-chunk",
                document_id=f"{tenant}-document",
                content="Fixture de test uniquement",
                score=0.8,
                metadata={"tenant_id": tenant, "domain": "droit", "country": "BJ"},
            )],
        )


def bearer(tenant_id):
    token = create_access_token(
        subject="lexia-contract-test",
        role=ApiRole.VIEWER,
        tenant_id=tenant_id,
    )
    return {"Authorization": f"Bearer {token}"}


def test_two_real_signed_jwts_have_isolated_retrieval(client):
    service = RecordingSearch()
    app.dependency_overrides[get_rag_search_service] = lambda: service
    try:
        a = client.post("/rag/lexia/search", headers=bearer("cabinet-a"),
                        json={"query": "foncier", "filters": {"country": "BJ", "domain": "droit"}})
        b = client.post("/rag/lexia/search", headers=bearer("cabinet-b"),
                        json={"query": "foncier", "filters": {"country": "BJ", "domain": "droit"}})
    finally:
        app.dependency_overrides.pop(get_rag_search_service, None)
    assert a.status_code == 200
    assert b.status_code == 200
    assert a.json()["results"][0]["document_id"] == "cabinet-a-document"
    assert b.json()["results"][0]["document_id"] == "cabinet-b-document"
    assert [x.metadata["tenant_id"] for x in service.calls] == ["cabinet-a", "cabinet-b"]


def test_signed_token_cannot_request_another_tenant(client):
    service = RecordingSearch()
    app.dependency_overrides[get_rag_search_service] = lambda: service
    try:
        response = client.post(
            "/rag/lexia/search", headers=bearer("cabinet-a"),
            json={"query": "foncier", "filters": {"tenant_id": "cabinet-b"}},
        )
    finally:
        app.dependency_overrides.pop(get_rag_search_service, None)
    assert response.status_code == 403
    assert not service.calls


def test_signed_token_without_tenant_fails_closed(client):
    service = RecordingSearch()
    app.dependency_overrides[get_rag_search_service] = lambda: service
    try:
        response = client.post(
            "/rag/lexia/search", headers=bearer(None),
            json={"query": "foncier", "filters": {"tenant_id": "cabinet-a"}},
        )
    finally:
        app.dependency_overrides.pop(get_rag_search_service, None)
    assert response.status_code == 403
    assert not service.calls
