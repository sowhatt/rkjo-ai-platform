from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from rkjo_kernel.rag.retrieval_filters import RetrievalFilters
from rkjo_kernel.rag.semantic_search import SemanticSearchResponse


class SemanticSearchPort(Protocol):
    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> SemanticSearchResponse: ...


@dataclass(frozen=True, slots=True)
class KnowledgeContextItem:
    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: dict[str, object]


class RAGContextBridge:
    """Adapt RKJO semantic search results for the Context Engine."""

    def __init__(self, search_service: SemanticSearchPort) -> None:
        self._search_service = search_service

    def retrieve(
        self,
        query: str,
        *,
        limit: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> tuple[KnowledgeContextItem, ...]:
        if not query.strip():
            raise ValueError("Knowledge query must not be empty")
        if limit <= 0:
            raise ValueError("Knowledge limit must be greater than zero")

        response = self._search_service.search(
            query,
            limit=limit,
            filters=filters,
        )

        return tuple(
            KnowledgeContextItem(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                content=result.content,
                score=result.score,
                metadata=dict(result.metadata),
            )
            for result in response.results
        )
