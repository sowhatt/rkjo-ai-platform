"""MM-RAG-03: unaffiliated API credentials cannot read OCR evidence."""
import pytest
from rkjo_api.dependencies import get_rag_search_service, get_rag_answering_service
from rkjo_api.main import app
from rkjo_kernel.rag.semantic_search import SemanticSearchResponse
from rkjo_kernel.rag.generation_models import RAGAnswer


class SearchSpy:
    def __init__(self):
        self.calls = []

    def search(self, query, *, limit=5, filters=None):
        self.calls.append(filters)
        return SemanticSearchResponse(sanitized_query=query, result_count=0, results=[])


class AnswerSpy:
    def __init__(self):
        self.calls = []

    def answer(self, question, *, limit=5, filters=None):
        self.calls.append(filters)
        return RAGAnswer(answer="No evidence.", sanitized_query=question, sources=[])


@pytest.mark.parametrize("route,payload,dependency,spy_cls", [
    ("/rag/search", {"query": "optique"}, get_rag_search_service, SearchSpy),
    ("/rag/answer", {"question": "optique"}, get_rag_answering_service, AnswerSpy),
])
def test_unbound_credential_fails_closed(client, monkeypatch, route, payload, dependency, spy_cls):
    monkeypatch.delenv("RKJO_VIEWER_TENANT_ID", raising=False)
    spy = spy_cls()
    app.dependency_overrides[dependency] = lambda: spy
    try:
        result = client.post(
            route, headers={"X-API-Key": "rkjo-viewer-key"}, json=payload,
        )
    finally:
        app.dependency_overrides.pop(dependency, None)
    assert result.status_code == 403
    assert spy.calls == []


@pytest.mark.parametrize("route,payload,dependency,spy_cls", [
    ("/rag/search", {"query": "optique", "filters": {"tenant_id": "tenant-b"}},
     get_rag_search_service, SearchSpy),
    ("/rag/answer", {"question": "optique", "filters": {"tenant_id": "tenant-b"}},
     get_rag_answering_service, AnswerSpy),
])
def test_unbound_credential_cannot_choose_tenant(client, monkeypatch, route, payload, dependency, spy_cls):
    monkeypatch.delenv("RKJO_VIEWER_TENANT_ID", raising=False)
    spy = spy_cls()
    app.dependency_overrides[dependency] = lambda: spy
    try:
        result = client.post(
            route, headers={"X-API-Key": "rkjo-viewer-key"}, json=payload,
        )
    finally:
        app.dependency_overrides.pop(dependency, None)
    assert result.status_code == 403
    assert spy.calls == []


@pytest.mark.parametrize("route,payload,dependency,spy_cls", [
    ("/rag/search", {"query": "optique"}, get_rag_search_service, SearchSpy),
    ("/rag/answer", {"question": "optique"}, get_rag_answering_service, AnswerSpy),
])
def test_bound_viewer_receives_forced_tenant(client, route, payload, dependency, spy_cls):
    spy = spy_cls()
    app.dependency_overrides[dependency] = lambda: spy
    try:
        result = client.post(
            route, headers={"X-API-Key": "rkjo-viewer-key"}, json=payload,
        )
    finally:
        app.dependency_overrides.pop(dependency, None)
    assert result.status_code == 200
    assert len(spy.calls) == 1
    assert spy.calls[0].metadata["tenant_id"] == "tenant-a"


def test_api_upload_without_tenant_is_rejected(client, monkeypatch):
    monkeypatch.setenv("RKJO_RAG_OCR_API_ENABLED", "true")
    monkeypatch.delenv("RKJO_OPERATOR_TENANT_ID", raising=False)
    result = client.post(
        "/rag/ocr/documents",
        headers={"X-API-Key": "rkjo-operator-key"},
        files={"file": ("contract.pdf", b"%PDF-1.4\n", "application/pdf")},
    )
    assert result.status_code == 403
