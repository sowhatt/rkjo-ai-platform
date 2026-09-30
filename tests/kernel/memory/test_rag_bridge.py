from __future__ import annotations

from dataclasses import dataclass

import pytest

from rkjo_kernel.memory import ContextEngine, InMemoryMemoryStore
from rkjo_kernel.memory.rag_bridge import RAGContextBridge
from rkjo_kernel.mission.execution_context import ExecutionContext
from rkjo_kernel.rag.retrieval_filters import RetrievalFilters
from rkjo_kernel.rag.semantic_search import (
    SemanticSearchResponse,
    SemanticSearchResult,
)


@dataclass
class FakeSemanticSearch:
    response: SemanticSearchResponse

    def __post_init__(self) -> None:
        self.calls: list[tuple[str, int, RetrievalFilters | None]] = []

    def search(self, query, *, limit=5, filters=None):
        self.calls.append((query, limit, filters))
        return self.response


def response() -> SemanticSearchResponse:
    return SemanticSearchResponse(
        sanitized_query="fractions",
        result_count=1,
        results=[
            SemanticSearchResult(
                chunk_id="chunk-1",
                document_id="doc-1",
                content="Fractions use numerator and denominator.",
                score=0.91,
                metadata={"tenant_id": "tenant-a", "subject": "math"},
            )
        ],
    )


def context() -> ExecutionContext:
    return ExecutionContext(
        mission_id="mission-1",
        trace_id="trace-1",
        tenant_id="tenant-a",
    )


def test_bridge_adapts_existing_semantic_search_result() -> None:
    fake = FakeSemanticSearch(response())
    bridge = RAGContextBridge(fake)

    items = bridge.retrieve("fractions", limit=3)

    assert len(items) == 1
    assert items[0].chunk_id == "chunk-1"
    assert items[0].document_id == "doc-1"
    assert items[0].score == 0.91
    assert items[0].metadata["subject"] == "math"
    assert fake.calls == [("fractions", 3, None)]


def test_bridge_forwards_existing_rag_filters() -> None:
    fake = FakeSemanticSearch(response())
    bridge = RAGContextBridge(fake)
    filters = RetrievalFilters(metadata={"tenant_id": "tenant-a"})

    bridge.retrieve("fractions", filters=filters)

    assert fake.calls[0][2] is filters


def test_bridge_rejects_empty_query() -> None:
    bridge = RAGContextBridge(FakeSemanticSearch(response()))

    with pytest.raises(ValueError, match="query"):
        bridge.retrieve("   ")


def test_bridge_rejects_non_positive_limit() -> None:
    bridge = RAGContextBridge(FakeSemanticSearch(response()))

    with pytest.raises(ValueError, match="limit"):
        bridge.retrieve("fractions", limit=0)


def test_context_engine_adds_knowledge_without_converting_it_to_memory() -> None:
    fake = FakeSemanticSearch(response())
    engine = ContextEngine(
        InMemoryMemoryStore(),
        rag_bridge=RAGContextBridge(fake),
    )

    package = engine.build(
        context=context(),
        query="fractions",
        knowledge_limit=2,
    )

    assert package.items == ()
    assert len(package.knowledge_items) == 1
    assert package.knowledge_items[0].document_id == "doc-1"
    assert fake.calls[0][:2] == ("fractions", 2)


def test_context_engine_without_bridge_remains_backward_compatible() -> None:
    engine = ContextEngine(InMemoryMemoryStore())

    package = engine.build(
        context=context(),
        query="fractions",
    )

    assert package.knowledge_items == ()


def test_context_engine_does_not_query_rag_without_query() -> None:
    fake = FakeSemanticSearch(response())
    engine = ContextEngine(
        InMemoryMemoryStore(),
        rag_bridge=RAGContextBridge(fake),
    )

    package = engine.build(context=context())

    assert package.knowledge_items == ()
    assert fake.calls == []
