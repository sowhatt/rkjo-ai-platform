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
