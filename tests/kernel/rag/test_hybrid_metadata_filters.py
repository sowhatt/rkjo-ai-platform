from rkjo_kernel.rag.hybrid_retriever import (
    HybridRetriever,
)
from rkjo_kernel.rag.retrieval_filters import (
    RetrievalFilters,
)


class RecordingRetriever:
    def __init__(self):
        self.calls = []

    def retrieve(
        self,
        query,
        *,
        limit=5,
        filters=None,
    ):
        self.calls.append(
            (
                query,
                limit,
                filters,
            )
        )
        return []


def test_hybrid_propagates_same_filters_to_both_channels():
    vector = RecordingRetriever()
    lexical = RecordingRetriever()

    retriever = HybridRetriever(
        vector_retriever=vector,
        lexical_retriever=lexical,
    )

    filters = RetrievalFilters(
        metadata={
            "country": "benin",
            "domain": "agriculture",
        }
    )

    retriever.retrieve(
        "maïs",
        limit=8,
        filters=filters,
    )

    assert vector.calls == [
        (
            "maïs",
            8,
            filters,
        )
    ]

    assert lexical.calls == [
        (
            "maïs",
            8,
            filters,
        )
    ]
