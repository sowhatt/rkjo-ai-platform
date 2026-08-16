"""Privacy-aware semantic search service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rkjo_kernel.rag.privacy import (
    DocumentSanitizer,
    NoOpDocumentSanitizer,
)
from rkjo_kernel.rag.retriever import (
    Retriever,
)
from rkjo_kernel.rag.reranker import (
    NoOpReranker,
    Reranker,
)
from rkjo_kernel.rag.relevance_filter import (
    RelevanceFilter,
)


@dataclass(frozen=True, slots=True)
class SemanticSearchResult:
    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SemanticSearchResponse:
    sanitized_query: str
    result_count: int
    results: list[SemanticSearchResult]


class SemanticSearchService:
    """Perform semantic retrieval without embedding raw PII."""

    def __init__(
        self,
        *,
        retriever: Retriever,
        sanitizer: DocumentSanitizer | None = None,
        reranker: Reranker | None = None,
        relevance_filter: RelevanceFilter | None = None,
        candidate_multiplier: int = 1,
    ) -> None:
        self.retriever = retriever
        self.sanitizer = (
            sanitizer
            or NoOpDocumentSanitizer()
        )

        self.reranker = (
            reranker
            or NoOpReranker()
        )

        self.relevance_filter = (
            relevance_filter
            or RelevanceFilter()
        )

        if not 1 <= candidate_multiplier <= 20:
            raise ValueError(
                "candidate_multiplier must be "
                "between 1 and 20."
            )

        self.candidate_multiplier = (
            candidate_multiplier
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> SemanticSearchResponse:
        if not query.strip():
            raise ValueError(
                "Search query must not be empty."
            )

        if not 1 <= limit <= 20:
            raise ValueError(
                "Search limit must be between 1 and 20."
            )

        sanitized = self.sanitizer.sanitize(
            query
        )

        if not sanitized.content.strip():
            raise ValueError(
                "Sanitized search query must not be empty."
            )

        candidate_limit = min(
            limit * self.candidate_multiplier,
            100,
        )

        candidates = self.retriever.retrieve(
            sanitized.content,
            limit=candidate_limit,
        )

        reranked = self.reranker.rerank(
            sanitized.content,
            candidates,
        )

        selected = self.relevance_filter.filter(
            reranked,
            limit=limit,
        )

        retrieved = [
            item.retrieved
            for item in selected
        ]

        results = [
            SemanticSearchResult(
                chunk_id=item.chunk.chunk_id,
                document_id=(
                    item.chunk.document_id
                ),
                content=item.chunk.content,
                score=item.score,
                metadata=dict(
                    item.chunk.metadata
                ),
            )
            for item in retrieved
        ]

        return SemanticSearchResponse(
            sanitized_query=(
                sanitized.content
            ),
            result_count=len(results),
            results=results,
        )
