"""Vector storage abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math

from rkjo_kernel.rag.models import (
    DocumentChunk,
    RetrievedChunk,
)
from rkjo_kernel.rag.retrieval_filters import (
    RetrievalFilters,
)


@dataclass(frozen=True, slots=True)
class VectorRecord:
    chunk: DocumentChunk
    embedding: list[float]


class VectorStore(ABC):
    """Abstract vector storage contract."""

    @abstractmethod
    def add(
        self,
        *,
        chunk: DocumentChunk,
        embedding: list[float],
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        *,
        query_embedding: list[float],
        limit: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> list[RetrievedChunk]:
        raise NotImplementedError


class InMemoryVectorStore(
    VectorStore
):
    """In-memory cosine-similarity vector store."""

    def __init__(self) -> None:
        self._records: list[
            VectorRecord
        ] = []

    def add(
        self,
        *,
        chunk: DocumentChunk,
        embedding: list[float],
    ) -> None:
        if not embedding:
            raise ValueError(
                "Embedding must not be empty."
            )

        self._records.append(
            VectorRecord(
                chunk=chunk,
                embedding=list(
                    embedding
                ),
            )
        )

    def search(
        self,
        *,
        query_embedding: list[float],
        limit: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> list[RetrievedChunk]:
        if not query_embedding:
            raise ValueError(
                "Query embedding must not be empty."
            )

        if limit <= 0:
            raise ValueError(
                "Search limit must be greater than 0."
            )

        active_filters = (
            filters
            or RetrievalFilters()
        )

        scored = [
            RetrievedChunk(
                chunk=record.chunk,
                score=self._cosine_similarity(
                    query_embedding,
                    record.embedding,
                ),
            )
            for record in self._records
            if active_filters.matches(
                record.chunk.metadata
            )
        ]

        return sorted(
            scored,
            key=lambda item: item.score,
            reverse=True,
        )[:limit]

    @staticmethod
    def _cosine_similarity(
        left: list[float],
        right: list[float],
    ) -> float:
        if len(left) != len(right):
            raise ValueError(
                "Embedding dimensions must match."
            )

        dot = sum(
            a * b
            for a, b in zip(
                left,
                right,
            )
        )

        left_norm = math.sqrt(
            sum(
                value * value
                for value in left
            )
        )

        right_norm = math.sqrt(
            sum(
                value * value
                for value in right
            )
        )

        if (
            left_norm == 0
            or right_norm == 0
        ):
            return 0.0

        return (
            dot
            / (
                left_norm
                * right_norm
            )
        )
