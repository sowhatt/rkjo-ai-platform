import pytest

from rkjo_kernel.rag.models import (
    DocumentChunk,
    RetrievedChunk,
)
from rkjo_kernel.rag.reranker import (
    LexicalOverlapReranker,
    NoOpReranker,
)


def candidate(
    *,
    document_id,
    content,
    score,
):
    return RetrievedChunk(
        chunk=DocumentChunk(
            document_id=document_id,
            chunk_id=f"{document_id}-chunk",
            content=content,
            chunk_index=0,
        ),
        score=score,
    )


def test_noop_preserves_vector_order():
    result = NoOpReranker().rerank(
        "question",
        [
            candidate(
                document_id="a",
                content="first",
                score=0.9,
            ),
            candidate(
                document_id="b",
                content="second",
                score=0.8,
            ),
        ],
    )

    assert [
        item.retrieved.chunk.document_id
        for item in result
    ] == ["a", "b"]


def test_noop_uses_vector_score_as_rerank_score():
    result = NoOpReranker().rerank(
        "question",
        [
            candidate(
                document_id="a",
                content="first",
                score=0.73,
            )
        ],
    )

    assert result[0].rerank_score == 0.73


def test_lexical_reranker_reorders_results():
    result = LexicalOverlapReranker().rerank(
        "sécheresse rendement maïs",
        [
            candidate(
                document_id="vector-first",
                content="Agriculture générale.",
                score=0.95,
            ),
            candidate(
                document_id="relevant",
                content=(
                    "La sécheresse réduit "
                    "le rendement du maïs."
                ),
                score=0.50,
            ),
        ],
    )

    assert (
        result[0].retrieved.chunk.document_id
        == "relevant"
    )

    assert result[0].rerank_score > 0.0


def test_vector_score_is_preserved():
    result = LexicalOverlapReranker().rerank(
        "sécheresse maïs",
        [
            candidate(
                document_id="doc",
                content="sécheresse maïs",
                score=0.42,
            )
        ],
    )

    assert result[0].vector_score == 0.42


def test_empty_query_is_rejected():
    with pytest.raises(
        ValueError,
        match="empty",
    ):
        LexicalOverlapReranker().rerank(
            " ",
            [],
        )
