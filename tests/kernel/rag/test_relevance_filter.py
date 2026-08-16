from rkjo_kernel.rag.models import (
    DocumentChunk,
    RetrievedChunk,
)
from rkjo_kernel.rag.relevance_filter import (
    RelevanceFilter,
    RelevanceFilterConfig,
)
from rkjo_kernel.rag.reranking_models import (
    RerankedChunk,
)


def item(
    document_id,
    rerank_score,
):
    return RerankedChunk(
        retrieved=RetrievedChunk(
            chunk=DocumentChunk(
                document_id=document_id,
                chunk_id=f"{document_id}-1",
                content=document_id,
                chunk_index=0,
            ),
            score=0.5,
        ),
        rerank_score=rerank_score,
    )


def test_filter_removes_weak_candidates():
    relevance_filter = RelevanceFilter(
        RelevanceFilterConfig(
            minimum_score=0.20,
            relative_to_top=0.50,
        )
    )

    result = relevance_filter.filter(
        [
            item("relevant", 0.80),
            item("weak", 0.30),
            item("noise", 0.05),
        ],
        limit=5,
    )

    assert [
        value.retrieved.chunk.document_id
        for value in result
    ] == ["relevant"]


def test_relative_threshold_keeps_close_results():
    relevance_filter = RelevanceFilter(
        RelevanceFilterConfig(
            minimum_score=0.10,
            relative_to_top=0.50,
        )
    )

    result = relevance_filter.filter(
        [
            item("a", 0.80),
            item("b", 0.50),
            item("c", 0.30),
        ],
        limit=5,
    )

    assert [
        value.retrieved.chunk.document_id
        for value in result
    ] == ["a", "b"]


def test_minimum_results_protects_empty_selection():
    relevance_filter = RelevanceFilter(
        RelevanceFilterConfig(
            minimum_score=0.90,
            relative_to_top=1.0,
            minimum_results=1,
        )
    )

    result = relevance_filter.filter(
        [
            item("best", 0.10),
            item("other", 0.05),
        ],
        limit=5,
    )

    assert len(result) == 1
    assert (
        result[0].retrieved.chunk.document_id
        == "best"
    )


def test_filter_respects_limit():
    relevance_filter = RelevanceFilter(
        RelevanceFilterConfig(
            minimum_score=0.0,
            relative_to_top=0.0,
        )
    )

    result = relevance_filter.filter(
        [
            item("a", 0.9),
            item("b", 0.8),
            item("c", 0.7),
        ],
        limit=2,
    )

    assert len(result) == 2


def test_empty_candidates_return_empty():
    assert (
        RelevanceFilter().filter(
            [],
            limit=5,
        )
        == []
    )
