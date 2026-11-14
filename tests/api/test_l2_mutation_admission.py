"""Refusal precedes even dependency construction, regardless of payload validity."""
import pytest
from rkjo_api.main import app
from rkjo_api.dependencies import get_rag_ingestion_pipeline, get_rag_document_replacement_service, get_rag_document_lifecycle_service

@pytest.mark.parametrize("method,path,dependency",[
    ("POST","/rag/documents",get_rag_ingestion_pipeline),
    ("PUT","/rag/documents/legacy",get_rag_document_replacement_service),
    ("DELETE","/rag/documents/legacy",get_rag_document_lifecycle_service),
])
def test_unbound_mutation_does_not_construct_service(client,monkeypatch,method,path,dependency):
    monkeypatch.delenv("RKJO_ADMIN_TENANT_ID",raising=False)
    def forbidden(): raise AssertionError("Service factory must not be called")
    app.dependency_overrides[dependency] = forbidden
    try:
        assert client.request(method,path,headers={"X-API-Key":"rkjo-admin-key"}).status_code == 403
    finally:
        app.dependency_overrides.pop(dependency,None)
