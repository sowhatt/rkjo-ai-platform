import pytest

from rkjo_kernel.rag.models import (
    DocumentChunk,
)
from rkjo_kernel.rag.retrieval_filters import (
    RetrievalFilters,
)
from rkjo_kernel.rag.vector_store import (
    InMemoryVectorStore,
)


def test_filters_match_exact_metadata():
    filters = RetrievalFilters(
        metadata={
            "country": "benin",
            "domain": "agriculture",
        }
    )

    assert filters.matches(
        {
            "country": "benin",
            "domain": "agriculture",
            "year": 2026,
        }
    )

    assert not filters.matches(
        {
            "country": "benin",
            "domain": "sante",
        }
    )


def test_empty_filters_match_everything():
    filters = RetrievalFilters()

    assert filters.is_empty is True
    assert filters.matches({}) is True
    assert filters.matches(
        {"domain": "anything"}
    ) is True


def test_invalid_nested_filter_is_rejected():
    with pytest.raises(
        ValueError,
        match="scalar JSON values",
    ):
        RetrievalFilters(
            metadata={
                "domain": {
                    "name": "agriculture"
                }
            }
        )


def test_in_memory_vector_store_filters_before_limit():
    store = InMemoryVectorStore()

    store.add(
        chunk=DocumentChunk(
            document_id="health",
            chunk_id="health-1",
            content="health",
            chunk_index=0,
            metadata={
                "domain": "sante",
            },
        ),
        embedding=[1.0, 0.0],
    )

    store.add(
        chunk=DocumentChunk(
            document_id="agriculture",
            chunk_id="agriculture-1",
            content="agriculture",
            chunk_index=0,
            metadata={
                "domain": "agriculture",
            },
        ),
        embedding=[0.9, 0.1],
    )

    results = store.search(
        query_embedding=[
            1.0,
            0.0,
        ],
        limit=1,
        filters=RetrievalFilters(
            metadata={
                "domain": "agriculture"
            }
        ),
    )

    assert len(results) == 1
    assert (
        results[0].chunk.document_id
        == "agriculture"
    )
