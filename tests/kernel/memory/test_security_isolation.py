from __future__ import annotations

from types import SimpleNamespace

import pytest

from rkjo_kernel.memory import ContextEngine, InMemoryMemoryStore, RAGContextBridge
from rkjo_kernel.mission.execution_context import ExecutionContext
from rkjo_kernel.rag.retrieval_filters import RetrievalFilters


class RecordingSearch:
    def __init__(self) -> None:
        self.filters = None

    def search(self, query, *, limit=5, filters=None):
        self.filters = filters
        return SimpleNamespace(results=[])


def execution_context(**kwargs):
    values = {
        "mission_id": "mission-1",
        "trace_id": "trace-1",
        "tenant_id": "tenant-a",
    }
    values.update(kwargs)
    return ExecutionContext(**values)


def test_execution_metadata_cannot_override_canonical_identity():
    context = execution_context(
        metadata={
            "tenant_id": "tenant-evil",
            "mission_id": "mission-evil",
            "trace_id": "trace-evil",
            "custom": "kept",
        }
    )

    metadata = context.as_metadata()

    assert metadata["tenant_id"] == "tenant-a"
    assert metadata["mission_id"] == "mission-1"
    assert metadata["trace_id"] == "trace-1"
    assert metadata["custom"] == "kept"


def test_context_engine_injects_tenant_into_rag_filters():
    search = RecordingSearch()
    engine = ContextEngine(
        InMemoryMemoryStore(),
        rag_bridge=RAGContextBridge(search),
    )

    engine.build(
        context=execution_context(),
        query="private knowledge",
    )

    assert search.filters == RetrievalFilters(
        metadata={"tenant_id": "tenant-a"}
    )


def test_context_engine_preserves_safe_filters_and_adds_tenant():
    search = RecordingSearch()
    engine = ContextEngine(
        InMemoryMemoryStore(),
        rag_bridge=RAGContextBridge(search),
    )

    engine.build(
        context=execution_context(),
        query="private knowledge",
        knowledge_filters=RetrievalFilters(
            metadata={"domain": "education"}
        ),
    )

    assert search.filters == RetrievalFilters(
        metadata={
            "domain": "education",
            "tenant_id": "tenant-a",
        }
    )


def test_context_engine_rejects_conflicting_rag_tenant_filter():
    search = RecordingSearch()
    engine = ContextEngine(
        InMemoryMemoryStore(),
        rag_bridge=RAGContextBridge(search),
    )

    with pytest.raises(ValueError, match="conflicts"):
        engine.build(
            context=execution_context(),
            query="private knowledge",
            knowledge_filters=RetrievalFilters(
                metadata={"tenant_id": "tenant-b"}
            ),
        )

    assert search.filters is None
