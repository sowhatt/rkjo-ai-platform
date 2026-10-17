"""Opt-in REAL PostgreSQL/pgvector + JWT + HTTP tenant isolation test.

Requires RKJO_LEXIA_TEST_DATABASE_URL pointing to a disposable PostgreSQL
database with pgvector available. Never uses production database by default.
No OpenAI calls. Creates and drops a uniquely named table in all cases.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest

from rkjo_api.dependencies import get_rag_search_service
from rkjo_api.jwt_auth import create_access_token
from rkjo_api.main import app
from rkjo_api.security import ApiRole
from rkjo_kernel.rag.models import DocumentChunk
from rkjo_kernel.rag.postgres_vector_store import PostgresPgVectorStore
from rkjo_kernel.rag.semantic_search import SemanticSearchService


class StoredVectorRetriever:
    def __init__(self, store):
        self.store = store

    def retrieve(self, query, *, limit=5, filters=None):
        # Fixed deterministic embedding ensures the database, not OpenAI,
        # performs the cosine distance search and tenant JSONB filtering.
        return self.store.search(
            query_embedding=[1.0, 0.0, 0.0],
            limit=limit,
            filters=filters,
        )


def headers(tenant):
    token = create_access_token(
        subject="lexia-pgvector-e2e",
        role=ApiRole.VIEWER,
        tenant_id=tenant,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
def test_lexia_real_pgvector_search_is_tenant_scoped(client):
    database_url = os.getenv("RKJO_LEXIA_TEST_DATABASE_URL", "").strip()
    if not database_url:
        pytest.skip("Set RKJO_LEXIA_TEST_DATABASE_URL to a disposable pgvector database")

    # Safe, isolated table name: never touch the application's rag_chunks.
    table_name = "lexia_e2e_" + uuid4().hex[:20]
    store = PostgresPgVectorStore(
        database_url=database_url, dimensions=3, table_name=table_name
    )
    try:
        store.initialize_schema()
        for tenant in ("cabinet-a", "cabinet-b"):
            store.add(
                chunk=DocumentChunk(
                    document_id=f"{tenant}-doc",
                    chunk_id=f"{tenant}-chunk",
                    chunk_index=0,
                    content=f"Texte juridique factice réservé à {tenant}",
                    metadata={
                        "tenant_id": tenant,
                        "country": "BJ",
                        "domain": "droit",
                        "title": "Document de test",
                        "article": "Article test",
                        "source": "fixture",
                    },
                ),
                embedding=[1.0, 0.0, 0.0],
            )

        search_service = SemanticSearchService(
            retriever=StoredVectorRetriever(store)
        )
        app.dependency_overrides[get_rag_search_service] = lambda: search_service
        try:
            for tenant in ("cabinet-a", "cabinet-b"):
                response = client.post(
                    "/rag/lexia/search",
                    headers=headers(tenant),
                    json={
                        "query": "texte juridique",
                        "filters": {"country": "BJ", "domain": "droit"},
                    },
                )
                assert response.status_code == 200, response.text
                results = response.json()["results"]
                assert len(results) == 1
                assert results[0]["document_id"] == f"{tenant}-doc"
                assert results[0]["metadata"]["tenant_id"] == tenant

            forbidden = client.post(
                "/rag/lexia/search",
                headers=headers("cabinet-a"),
                json={"query": "texte juridique", "filters": {"tenant_id": "cabinet-b"}},
            )
            assert forbidden.status_code == 403
        finally:
            app.dependency_overrides.pop(get_rag_search_service, None)
    finally:
        store.drop_schema()
