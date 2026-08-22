import pytest

from rkjo_kernel.rag.context_builder import (
    CitationContextBuilder,
)
from rkjo_kernel.rag.semantic_search import (
    SemanticSearchResult,
)


def result(
    *,
    chunk_id,
    document_id,
    content,
    score=0.8,
):
    return SemanticSearchResult(
        chunk_id=chunk_id,
        document_id=document_id,
        content=content,
        score=score,
        metadata={},
    )


def test_context_builder_adds_citation_markers():
    builder = CitationContextBuilder(
        max_characters=1000
    )

    built = builder.build(
        [
            result(
                chunk_id="chunk-1",
                document_id="doc-1",
                content="First source.",
            ),
            result(
                chunk_id="chunk-2",
                document_id="doc-2",
                content="Second source.",
            ),
        ]
    )

    assert "[1]" in built.content
    assert "[2]" in built.content
    assert "First source." in built.content
    assert "Second source." in built.content
    assert len(built.results) == 2


def test_context_builder_respects_character_limit():
    builder = CitationContextBuilder(
        max_characters=90
    )

    built = builder.build(
        [
            result(
                chunk_id="c1",
                document_id="d1",
                content="short",
            ),
            result(
                chunk_id="c2",
                document_id="d2",
                content="x" * 200,
            ),
        ]
    )

    assert len(built.results) == 1
    assert "[1]" in built.content
    assert "[2]" not in built.content
    assert built.truncated is True


def test_context_builder_respects_max_chunks():
    builder = CitationContextBuilder(
        max_characters=1000,
        max_chunks=2,
    )

    built = builder.build(
        [
            result(
                chunk_id="c1",
                document_id="d1",
                content="first",
            ),
            result(
                chunk_id="c2",
                document_id="d2",
                content="second",
            ),
            result(
                chunk_id="c3",
                document_id="d3",
                content="third",
            ),
        ]
    )

    assert len(built.results) == 2
    assert [
        item.chunk_id
        for item in built.results
    ] == ["c1", "c2"]
    assert built.truncated is True


def test_context_builder_skips_oversized_chunk_and_continues():
    first = result(
        chunk_id="c1",
        document_id="d1",
        content="first",
    )
    oversized = result(
        chunk_id="c2",
        document_id="d2",
        content="x" * 500,
    )
    last = result(
        chunk_id="c3",
        document_id="d3",
        content="last",
    )

    first_only = CitationContextBuilder(
        max_characters=1000
    ).build([first])

    last_only = CitationContextBuilder(
        max_characters=1000
    ).build([last])

    budget = (
        first_only.character_count
        + 2
        + last_only.character_count
    )

    built = CitationContextBuilder(
        max_characters=budget,
        max_chunks=3,
    ).build(
        [first, oversized, last]
    )

    assert [
        item.chunk_id
        for item in built.results
    ] == ["c1", "c3"]
    assert built.truncated is True
    assert built.character_count <= budget


def test_context_builder_deduplicates_same_document_content():
    built = CitationContextBuilder(
        max_characters=1000
    ).build(
        [
            result(
                chunk_id="c1",
                document_id="d1",
                content="same source",
            ),
            result(
                chunk_id="c2",
                document_id="d1",
                content="same source",
            ),
        ]
    )

    assert len(built.results) == 1
    assert built.results[0].chunk_id == "c1"
    assert built.truncated is False


def test_context_builder_preserves_same_content_from_different_documents():
    built = CitationContextBuilder(
        max_characters=1000
    ).build(
        [
            result(
                chunk_id="c1",
                document_id="d1",
                content="shared text",
            ),
            result(
                chunk_id="c2",
                document_id="d2",
                content="shared text",
            ),
        ]
    )

    assert len(built.results) == 2
    assert [
        item.document_id
        for item in built.results
    ] == ["d1", "d2"]


def test_context_builder_character_count_matches_content():
    built = CitationContextBuilder(
        max_characters=1000
    ).build(
        [
            result(
                chunk_id="c1",
                document_id="d1",
                content="measured content",
            )
        ]
    )

    assert built.character_count == len(
        built.content
    )
    assert built.truncated is False


def test_context_builder_rejects_invalid_max_chunks():
    with pytest.raises(
        ValueError,
        match="max_chunks",
    ):
        CitationContextBuilder(
            max_chunks=0
        )
