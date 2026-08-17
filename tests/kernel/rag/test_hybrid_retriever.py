import pytest

from rkjo_kernel.rag.hybrid_retriever import (
    HybridRetriever,
    ReciprocalRankFusion,
)
from rkjo_kernel.rag.models import (
    DocumentChunk,
    RetrievedChunk,
)


def item(
    document_id,
    score,
):
    return RetrievedChunk(
        chunk=DocumentChunk(
            document_id=document_id,
            chunk_id=f"{document_id}-chunk",
            content=document_id,
            chunk_index=0,
        ),
        score=score,
    )


class FakeRetriever:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def retrieve(
        self,
        query,
        *,
        limit=5,
    ):
        self.calls.append(
            (query, limit)
        )

        return self.results[:limit]


def test_rrf_rewards_document_present_in_both_rankings():
    fusion = ReciprocalRankFusion(
        k=60
    )

    result = fusion.fuse(
        vector_results=[
            item("vector-only", 0.95),
            item("shared", 0.80),
        ],
        lexical_results=[
            item("shared", 0.90),
            item("lexical-only", 0.70),
        ],
        limit=3,
    )

    assert (
        result[0].chunk.document_id
        == "shared"
    )


def test_rrf_deduplicates_chunks():
    result = ReciprocalRankFusion().fuse(
        vector_results=[
            item("same", 0.9),
        ],
        lexical_results=[
            item("same", 0.8),
        ],
        limit=5,
    )

    assert len(result) == 1


def test_rrf_score_is_independent_of_raw_channel_scores():
    result = ReciprocalRankFusion(
        k=60
    ).fuse(
        vector_results=[
            item("a", 999.0),
        ],
        lexical_results=[],
        limit=1,
    )

    assert result[0].score == pytest.approx(
        1.0 / 61.0
    )


def test_hybrid_retriever_calls_both_channels():
    vector = FakeRetriever(
        [item("vector", 0.9)]
    )

    lexical = FakeRetriever(
        [item("lexical", 0.8)]
    )

    retriever = HybridRetriever(
        vector_retriever=vector,
        lexical_retriever=lexical,
    )

    retriever.retrieve(
        "AGRIREF2026",
        limit=3,
    )

    assert vector.calls == [
        ("AGRIREF2026", 3)
    ]

    assert lexical.calls == [
        ("AGRIREF2026", 3)
    ]


def test_rrf_rejects_invalid_k():
    with pytest.raises(
        ValueError,
        match="greater than 0",
    ):
        ReciprocalRankFusion(k=0)


def test_hybrid_rejects_empty_query():
    retriever = HybridRetriever(
        vector_retriever=FakeRetriever([]),
        lexical_retriever=FakeRetriever([]),
    )

    with pytest.raises(
        ValueError,
        match="empty",
    ):
        retriever.retrieve(
            " ",
            limit=5,
        )
