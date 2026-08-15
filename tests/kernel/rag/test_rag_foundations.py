import pytest

from rkjo_kernel.rag.chunking import TextChunker
from rkjo_kernel.rag.embedding import (
    DeterministicEmbeddingProvider,
)
from rkjo_kernel.rag.models import Document
from rkjo_kernel.rag.retriever import Retriever
from rkjo_kernel.rag.vector_store import (
    InMemoryVectorStore,
)


def test_document_requires_content():
    with pytest.raises(
        ValueError,
        match="content",
    ):
        Document(
            content=" "
        )


def test_chunker_splits_document():
    document = Document(
        content="abcdefghij"
    )

    chunker = TextChunker(
        chunk_size=4,
        overlap=1,
    )

    chunks = chunker.split(
        document
    )

    assert len(chunks) == 3

    assert [
        chunk.content
        for chunk in chunks
    ] == [
        "abcd",
        "defg",
        "ghij",
    ]


def test_document_metadata_is_copied_to_chunks():
    document = Document(
        content="abcdefgh",
        metadata={
            "source": "manual"
        },
    )

    chunks = TextChunker(
        chunk_size=4,
        overlap=0,
    ).split(
        document
    )

    assert chunks[0].metadata[
        "source"
    ] == "manual"


def test_embedding_is_deterministic():
    provider = (
        DeterministicEmbeddingProvider(
            dimensions=8
        )
    )

    first = provider.embed(
        "weather"
    )

    second = provider.embed(
        "weather"
    )

    assert first == second

    assert len(first) == 8


def test_vector_store_returns_best_match():
    provider = (
        DeterministicEmbeddingProvider(
            dimensions=16
        )
    )

    store = InMemoryVectorStore()

    retriever = Retriever(
        chunker=TextChunker(
            chunk_size=100,
            overlap=0,
        ),
        embedding_provider=provider,
        vector_store=store,
    )

    retriever.ingest(
        Document(
            content=(
                "rain drought climate"
            ),
            document_id="climate",
        )
    )

    retriever.ingest(
        Document(
            content=(
                "bank insurance contract"
            ),
            document_id="insurance",
        )
    )

    results = retriever.retrieve(
        "rain drought climate",
        limit=1,
    )

    assert len(results) == 1

    assert (
        results[0]
        .chunk
        .document_id
        == "climate"
    )


def test_ingest_returns_chunk_count():
    retriever = Retriever(
        chunker=TextChunker(
            chunk_size=5,
            overlap=0,
        ),
        embedding_provider=(
            DeterministicEmbeddingProvider()
        ),
        vector_store=(
            InMemoryVectorStore()
        ),
    )

    count = retriever.ingest(
        Document(
            content="abcdefghij"
        )
    )

    assert count == 2


def test_retrieve_rejects_empty_query():
    retriever = Retriever(
        chunker=TextChunker(),
        embedding_provider=(
            DeterministicEmbeddingProvider()
        ),
        vector_store=(
            InMemoryVectorStore()
        ),
    )

    with pytest.raises(
        ValueError,
        match="query",
    ):
        retriever.retrieve(
            " "
        )
