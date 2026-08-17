"""Hybrid vector + lexical retrieval using RRF."""

from __future__ import annotations

from dataclasses import dataclass

from rkjo_kernel.rag.models import (
    RetrievedChunk,
)


@dataclass(frozen=True, slots=True)
class FusionCandidate:
    retrieved: RetrievedChunk
    fused_score: float
    vector_rank: int | None
    lexical_rank: int | None


class ReciprocalRankFusion:
    """Fuse ranked result lists without comparing raw scores."""

    def __init__(
        self,
        *,
        k: int = 60,
    ) -> None:
        if k <= 0:
            raise ValueError(
                "RRF k must be greater than 0."
            )

        self.k = k

    def fuse(
        self,
        *,
        vector_results: list[RetrievedChunk],
        lexical_results: list[RetrievedChunk],
        limit: int,
    ) -> list[RetrievedChunk]:
        if limit <= 0:
            raise ValueError(
                "Fusion limit must be greater than 0."
            )

        candidates: dict[
            str,
            dict[str, object],
        ] = {}

        for rank, item in enumerate(
            vector_results,
            start=1,
        ):
            key = item.chunk.chunk_id

            candidates.setdefault(
                key,
                {
                    "retrieved": item,
                    "score": 0.0,
                    "vector_rank": None,
                    "lexical_rank": None,
                },
            )

            candidates[key]["score"] = (
                float(
                    candidates[key]["score"]
                )
                + 1.0 / (self.k + rank)
            )

            candidates[key]["vector_rank"] = rank

        for rank, item in enumerate(
            lexical_results,
            start=1,
        ):
            key = item.chunk.chunk_id

            candidates.setdefault(
                key,
                {
                    "retrieved": item,
                    "score": 0.0,
                    "vector_rank": None,
                    "lexical_rank": None,
                },
            )

            candidates[key]["score"] = (
                float(
                    candidates[key]["score"]
                )
                + 1.0 / (self.k + rank)
            )

            candidates[key]["lexical_rank"] = rank

        ordered = sorted(
            candidates.items(),
            key=lambda pair: (
                -float(
                    pair[1]["score"]
                ),
                pair[0],
            ),
        )

        return [
            RetrievedChunk(
                chunk=(
                    data["retrieved"].chunk
                ),
                score=float(
                    data["score"]
                ),
            )
            for _, data in ordered[:limit]
        ]


class HybridRetriever:
    """Combine semantic vector and lexical retrieval."""

    def __init__(
        self,
        *,
        vector_retriever,
        lexical_retriever,
        fusion: ReciprocalRankFusion | None = None,
    ) -> None:
        self.vector_retriever = (
            vector_retriever
        )
        self.lexical_retriever = (
            lexical_retriever
        )
        self.fusion = (
            fusion
            or ReciprocalRankFusion()
        )

    def retrieve(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[RetrievedChunk]:
        if not query.strip():
            raise ValueError(
                "Hybrid retrieval query must not be empty."
            )

        if limit <= 0:
            raise ValueError(
                "Hybrid retrieval limit must be "
                "greater than 0."
            )

        vector_results = (
            self.vector_retriever.retrieve(
                query,
                limit=limit,
            )
        )

        lexical_results = (
            self.lexical_retriever.retrieve(
                query,
                limit=limit,
            )
        )

        return self.fusion.fuse(
            vector_results=vector_results,
            lexical_results=lexical_results,
            limit=limit,
        )
