from rkjo_kernel.rag.chunking import (
    TextChunker,
)
from rkjo_kernel.rag.deduplication import (
    InMemoryDocumentHashRegistry,
)
from rkjo_kernel.rag.embedding import (
    EmbeddingProvider,
)
from rkjo_kernel.rag.ingestion import (
    DocumentIngestionPipeline,
)
from rkjo_kernel.rag.loaders import (
    CompositeDocumentLoader,
)
from rkjo_kernel.rag.privacy import (
    RuleBasedPIISanitizer,
    SanitizationMode,
)
from rkjo_kernel.rag.retriever import (
    Retriever,
)
from rkjo_kernel.rag.vector_store import (
    InMemoryVectorStore,
)


class RecordingEmbeddingProvider(
    EmbeddingProvider
):
    def __init__(self) -> None:
        self.inputs: list[str] = []

    def embed(
        self,
        text: str,
    ) -> list[float]:
        self.inputs.append(
            text
        )

        return [
            1.0,
            0.0,
            0.0,
            0.0,
        ]


def test_pii_is_removed_before_embedding(
    tmp_path,
):
    path = tmp_path / "patient.txt"

    path.write_text(
        (
            "Contact jean@example.com "
            "on +33 6 12 34 56 78."
        ),
        encoding="utf-8",
    )

    embeddings = (
        RecordingEmbeddingProvider()
    )

    pipeline = (
        DocumentIngestionPipeline(
            loader=(
                CompositeDocumentLoader()
            ),
            retriever=Retriever(
                chunker=TextChunker(
                    chunk_size=500,
                    overlap=0,
                ),
                embedding_provider=(
                    embeddings
                ),
                vector_store=(
                    InMemoryVectorStore()
                ),
            ),
            hash_registry=(
                InMemoryDocumentHashRegistry()
            ),
            sanitizer=(
                RuleBasedPIISanitizer(
                    mode=(
                        SanitizationMode.REDACT
                    )
                )
            ),
        )
    )

    result = pipeline.ingest_file(
        path,
        document_id="privacy-001",
    )

    assert result.duplicate is False
    assert len(embeddings.inputs) == 1

    embedded_text = (
        embeddings.inputs[0]
    )

    assert (
        "jean@example.com"
        not in embedded_text
    )

    assert (
        "+33 6 12 34 56 78"
        not in embedded_text
    )

    assert "[EMAIL]" in embedded_text
    assert "[PHONE]" in embedded_text


def test_sanitized_metadata_reaches_vector_store(
    tmp_path,
):
    path = tmp_path / "contact.txt"

    path.write_text(
        "Email privacy@example.com",
        encoding="utf-8",
    )

    store = InMemoryVectorStore()

    pipeline = (
        DocumentIngestionPipeline(
            loader=(
                CompositeDocumentLoader()
            ),
            retriever=Retriever(
                chunker=TextChunker(
                    chunk_size=500,
                    overlap=0,
                ),
                embedding_provider=(
                    RecordingEmbeddingProvider()
                ),
                vector_store=store,
            ),
            hash_registry=(
                InMemoryDocumentHashRegistry()
            ),
            sanitizer=(
                RuleBasedPIISanitizer(
                    mode=(
                        SanitizationMode.REDACT
                    )
                )
            ),
        )
    )

    pipeline.ingest_file(
        path,
        document_id="privacy-002",
    )

    record = store._records[0]

    assert (
        "privacy@example.com"
        not in record.chunk.content
    )

    assert (
        record.chunk.metadata[
            "sanitization_mode"
        ]
        == "redact"
    )

    assert (
        record.chunk.metadata[
            "pii_detection_count"
        ]
        == 1
    )

    assert (
        record.chunk.metadata[
            "pii_categories"
        ]
        == ["email"]
    )


def test_hash_is_based_on_sanitized_content(
    tmp_path,
):
    first_path = (
        tmp_path / "first.txt"
    )

    second_path = (
        tmp_path / "second.txt"
    )

    first_path.write_text(
        "Contact alice@example.com",
        encoding="utf-8",
    )

    second_path.write_text(
        "Contact bob@example.com",
        encoding="utf-8",
    )

    registry = (
        InMemoryDocumentHashRegistry()
    )

    def make_pipeline():
        return (
            DocumentIngestionPipeline(
                loader=(
                    CompositeDocumentLoader()
                ),
                retriever=Retriever(
                    chunker=TextChunker(
                        chunk_size=500,
                        overlap=0,
                    ),
                    embedding_provider=(
                        RecordingEmbeddingProvider()
                    ),
                    vector_store=(
                        InMemoryVectorStore()
                    ),
                ),
                hash_registry=registry,
                sanitizer=(
                    RuleBasedPIISanitizer(
                        mode=(
                            SanitizationMode.REDACT
                        )
                    )
                ),
            )
        )

    first = make_pipeline().ingest_file(
        first_path
    )

    second = make_pipeline().ingest_file(
        second_path
    )

    # Both raw emails become the same safe token:
    # "Contact [EMAIL]".
    assert (
        first.content_hash
        == second.content_hash
    )

    assert first.duplicate is False
    assert second.duplicate is True
