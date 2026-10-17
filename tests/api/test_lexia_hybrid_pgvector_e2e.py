"""Real PostgreSQL vector + lexical hybrid search, scoped by signed JWT.

Opt-in: requires RKJO_LEXIA_TEST_DATABASE_URL for a disposable pgvector DB.
No OpenAI credentials or actual legal records are used.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest

from rkjo_api.dependencies import get_rag_search_service
from rkjo_api.jwt_auth import create_access_token
from rkjo_api.main import app
from rkjo_api.security import ApiRole
from rkjo_kernel.rag.hybrid_retriever import HybridRetriever, ReciprocalRankFusion
from rkjo_kernel.rag.models import DocumentChunk
from rkjo_kernel.rag.postgres_lexical_retriever import PostgresLexicalRetriever
from rkjo_kernel.rag.postgres_vector_store import PostgresPgVectorStore
from rkjo_kernel.rag.semantic_search import SemanticSearchService


class DeterministicVectorRetriever:
    def __init__(self, store):
        self.store = store

    def retrieve(self, query, *, limit=5, filters=None):
        return self.store.search(
            query_embedding=[1.0, 0.0, 0.0], limit=limit, filters=filters
        )


def signed_headers(tenant):
    return {"Authorization": "Bearer " + create_access_token(
        subject="lexia-hybrid-e2e",
        role=ApiRole.VIEWER,
        tenant_id=tenant,
    )}


@pytest.mark.integration
def test_lexia_hybrid_pgvector_and_lexical_are_tenant_scoped(client):
    url = os.environ.get("RKJO_LEXIA_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("RKJO_LEXIA_TEST_DATABASE_URL must reference disposable pgvector DB")

    table = "lexia_hybrid_e2e_" + uuid4().hex[:16]
    vector = PostgresPgVectorStore(database_url=url, dimensions=3, table_name=table)
    lexical = PostgresLexicalRetriever(database_url=url, table_name=table)
    created = False
    try:
        vector.initialize_schema()
        created = True
        lexical.initialize_schema()
        for tenant in ("cabinet-a", "cabinet-b"):
            vector.add(
                chunk=DocumentChunk(
                    document_id=tenant + "-hybrid-doc",
                    chunk_id=tenant + "-hybrid-chunk",
                    chunk_index=0,
                    content="Termes de test foncier donation succession " + tenant,
                    metadata={"tenant_id": tenant, "country": "BJ",
                              "domain": "droit", "source": "fixture"},
                ),
                embedding=[1.0, 0.0, 0.0],
            )

        service = SemanticSearchService(retriever=HybridRetriever(
            vector_retriever=DeterministicVectorRetriever(vector),
            lexical_retriever=lexical,
            fusion=ReciprocalRankFusion(),
        ))
        app.dependency_overrides[get_rag_search_service] = lambda: service
        try:
            for tenant in ("cabinet-a", "cabinet-b"):
                response = client.post(
                    "/rag/lexia/search",
                    headers=signed_headers(tenant),
                    json={"query": "foncier donation", "limit": 5,
                          "filters": {"country": "BJ", "domain": "droit"}},
                )
                assert response.status_code == 200, response.text
                rows = response.json()["results"]
                assert len(rows) == 1
                assert rows[0]["document_id"] == tenant + "-hybrid-doc"
                assert rows[0]["metadata"]["tenant_id"] == tenant

            denied = client.post(
                "/rag/lexia/search",
                headers=signed_headers("cabinet-a"),
                json={"query": "foncier", "filters": {"tenant_id": "cabinet-b"}},
            )
            assert denied.status_code == 403

            # Without client filters, server MUST still scope retrieval to JWT tenant.
            unfiltered = client.post(
                "/rag/lexia/search",
                headers=signed_headers("cabinet-a"),
                json={"query": "foncier donation", "limit": 10},
            )
            assert unfiltered.status_code == 200, unfiltered.text
            unfiltered_rows = unfiltered.json()["results"]
            assert len(unfiltered_rows) == 1
            assert unfiltered_rows[0]["metadata"]["tenant_id"] == "cabinet-a"

            # An authenticated but unbound JWT cannot choose its own tenant.
            unbound = client.post(
                "/rag/lexia/search",
                headers=signed_headers(None),
                json={"query": "foncier", "filters": {"tenant_id": "cabinet-a"}},
            )
            assert unbound.status_code == 403

            # Empty metadata match must not expand search to foreign documents.
            no_match = client.post(
                "/rag/lexia/search",
                headers=signed_headers("cabinet-a"),
                json={"query": "foncier", "filters": {"country": "FR"}},
            )
            assert no_match.status_code == 200, no_match.text
            assert no_match.json()["results"] == []
        finally:
            app.dependency_overrides.pop(get_rag_search_service, None)
    finally:
        if created:
            vector.drop_schema()
