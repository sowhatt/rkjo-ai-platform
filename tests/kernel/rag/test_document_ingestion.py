import pytest

from rkjo_kernel.rag.chunking import TextChunker
from rkjo_kernel.rag.deduplication import (
    InMemoryDocumentHashRegistry,
)
from rkjo_kernel.rag.embedding import (
    DeterministicEmbeddingProvider,
)
from rkjo_kernel.rag.hashing import (
    compute_content_hash,
)
from rkjo_kernel.rag.ingestion import (
    DocumentIngestionPipeline,
)
from rkjo_kernel.rag.loaders import (
    CompositeDocumentLoader,
)
from rkjo_kernel.rag.retriever import Retriever
from rkjo_kernel.rag.vector_store import (
    InMemoryVectorStore,
)


def make_pipeline():
    return DocumentIngestionPipeline(
        loader=CompositeDocumentLoader(),
        retriever=Retriever(
            chunker=TextChunker(
                chunk_size=20,
                overlap=0,
            ),
            embedding_provider=(
                DeterministicEmbeddingProvider(
                    dimensions=16
                )
            ),
            vector_store=(
                InMemoryVectorStore()
            ),
        ),
        hash_registry=(
            InMemoryDocumentHashRegistry()
        ),
    )


def test_hash_is_deterministic():
    first = compute_content_hash(
        "hello world"
    )

    second = compute_content_hash(
        "hello world"
    )

    assert first == second
    assert len(first) == 64


def test_txt_document_is_loaded(
    tmp_path,
):
    path = tmp_path / "sample.txt"

    path.write_text(
        "Hello    world\n\n\nRKJO",
        encoding="utf-8",
    )

    loaded = (
        CompositeDocumentLoader()
        .load(path)
    )

    assert loaded.content == (
        "Hello world\n\nRKJO"
    )

    assert loaded.source_type == "txt"


def test_markdown_document_is_loaded(
    tmp_path,
):
    path = tmp_path / "sample.md"

    path.write_text(
        "# Climate\n\nRainfall data",
        encoding="utf-8",
    )

    loaded = (
        CompositeDocumentLoader()
        .load(path)
    )

    assert "# Climate" in loaded.content
    assert loaded.source_type == "md"


def test_unsupported_format_is_rejected(
    tmp_path,
):
    path = tmp_path / "sample.csv"

    path.write_text(
        "a,b",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Unsupported",
    ):
        CompositeDocumentLoader().load(
            path
        )


def test_ingestion_indexes_real_text_file(
    tmp_path,
):
    path = tmp_path / "knowledge.txt"

    path.write_text(
        (
            "Climate rainfall agriculture "
            "soil crop yield"
        ),
        encoding="utf-8",
    )

    pipeline = make_pipeline()

    result = pipeline.ingest_file(
        path,
        document_id="doc-001",
        metadata={
            "product": "ADIP"
        },
    )

    assert result.duplicate is False
    assert result.document_id == "doc-001"
    assert result.chunk_count > 0


def test_duplicate_content_is_not_reindexed(
    tmp_path,
):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"

    first.write_text(
        "same knowledge",
        encoding="utf-8",
    )

    second.write_text(
        "same knowledge",
        encoding="utf-8",
    )

    pipeline = make_pipeline()

    first_result = pipeline.ingest_file(
        first
    )

    second_result = pipeline.ingest_file(
        second
    )

    assert first_result.duplicate is False
    assert second_result.duplicate is True
    assert second_result.chunk_count == 0

    assert (
        first_result.content_hash
        == second_result.content_hash
    )


def test_metadata_is_propagated(
    tmp_path,
):
    path = tmp_path / "doc.md"

    path.write_text(
        "Agricultural knowledge",
        encoding="utf-8",
    )

    store = InMemoryVectorStore()

    pipeline = DocumentIngestionPipeline(
        loader=CompositeDocumentLoader(),
        retriever=Retriever(
            chunker=TextChunker(
                chunk_size=100,
                overlap=0,
            ),
            embedding_provider=(
                DeterministicEmbeddingProvider(
                    dimensions=16
                )
            ),
            vector_store=store,
        ),
        hash_registry=(
            InMemoryDocumentHashRegistry()
        ),
    )

    pipeline.ingest_file(
        path,
        document_id="meta-001",
        metadata={
            "country": "benin"
        },
    )

    provider = (
        DeterministicEmbeddingProvider(
            dimensions=16
        )
    )

    results = store.search(
        query_embedding=provider.embed(
            "Agricultural knowledge"
        ),
        limit=1,
    )

    metadata = results[0].chunk.metadata

    assert metadata["country"] == "benin"
    assert metadata["source_type"] == "md"
    assert "content_hash" in metadata
