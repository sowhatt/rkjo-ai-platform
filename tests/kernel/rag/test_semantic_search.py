import pytest

from rkjo_kernel.rag.embedding import (
    EmbeddingProvider,
)
from rkjo_kernel.rag.models import (
    DocumentChunk,
)
from rkjo_kernel.rag.privacy import (
    RuleBasedPIISanitizer,
    SanitizationMode,
)
from rkjo_kernel.rag.retriever import (
    Retriever,
)
from rkjo_kernel.rag.semantic_search import (
    SemanticSearchService,
)
from rkjo_kernel.rag.vector_store import (
    InMemoryVectorStore,
)


class RecordingEmbeddingProvider(
    EmbeddingProvider
):
    def __init__(self):
        self.inputs = []

    def embed(
        self,
        text: str,
    ) -> list[float]:
        self.inputs.append(text)
        return [1.0, 0.0]


def make_service():
    provider = (
        RecordingEmbeddingProvider()
    )

    store = InMemoryVectorStore()

    chunk = DocumentChunk(
        document_id="doc-001",
        chunk_id="chunk-001",
        content=(
            "Le déficit pluviométrique "
            "affecte le rendement du maïs."
        ),
        chunk_index=0,
        metadata={
            "country": "benin"
        },
    )

    store.add(
        chunk=chunk,
        embedding=[
            1.0,
            0.0,
        ],
    )

    service = SemanticSearchService(
        retriever=Retriever(
            chunker=None,
            embedding_provider=provider,
            vector_store=store,
        ),
        sanitizer=(
            RuleBasedPIISanitizer(
                mode=(
                    SanitizationMode.REDACT
                )
            )
        ),
    )

    return service, provider


def test_search_returns_results():
    service, _ = make_service()

    result = service.search(
        "rendement maïs",
        limit=1,
    )

    assert result.result_count == 1

    assert (
        result.results[0].document_id
        == "doc-001"
    )


def test_query_pii_is_removed_before_embedding():
    service, provider = make_service()

    result = service.search(
        (
            "Que dit jean@example.com "
            "sur le rendement du maïs ?"
        ),
        limit=1,
    )

    assert len(provider.inputs) == 1

    assert (
        "jean@example.com"
        not in provider.inputs[0]
    )

    assert "[EMAIL]" in (
        provider.inputs[0]
    )

    assert (
        result.sanitized_query
        == provider.inputs[0]
    )


def test_search_rejects_empty_query():
    service, _ = make_service()

    with pytest.raises(
        ValueError,
        match="empty",
    ):
        service.search(" ")


def test_search_rejects_invalid_limit():
    service, _ = make_service()

    with pytest.raises(
        ValueError,
        match="between 1 and 20",
    ):
        service.search(
            "maïs",
            limit=21,
        )
