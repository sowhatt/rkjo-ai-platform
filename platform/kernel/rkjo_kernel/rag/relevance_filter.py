"""Post-reranking relevance filtering."""

from __future__ import annotations

from dataclasses import dataclass

from rkjo_kernel.rag.reranking_models import (
    RerankedChunk,
)


@dataclass(frozen=True, slots=True)
class RelevanceFilterConfig:
    minimum_score: float = 0.20
    relative_to_top: float = 0.50
    minimum_results: int = 1

    def __post_init__(self) -> None:
        if not 0.0 <= self.minimum_score <= 1.0:
            raise ValueError(
                "minimum_score must be between 0 and 1."
            )

        if not 0.0 <= self.relative_to_top <= 1.0:
            raise ValueError(
                "relative_to_top must be between 0 and 1."
            )

        if self.minimum_results < 0:
            raise ValueError(
                "minimum_results must be >= 0."
            )


class RelevanceFilter:
    """Remove weak candidates after reranking.

    A candidate survives when its reranking score is
    both above the absolute threshold and sufficiently
    close to the strongest candidate.

    minimum_results protects against an overly aggressive
    filter when at least one candidate should be retained.
    """

    def __init__(
        self,
        config: RelevanceFilterConfig | None = None,
    ) -> None:
        self.config = (
            config
            or RelevanceFilterConfig()
        )

    def filter(
        self,
        candidates: list[RerankedChunk],
        *,
        limit: int,
    ) -> list[RerankedChunk]:
        if limit <= 0:
            raise ValueError(
                "limit must be greater than 0."
            )

        if not candidates:
            return []

        top_score = candidates[0].rerank_score

        relative_threshold = (
            top_score
            * self.config.relative_to_top
        )

        threshold = max(
            self.config.minimum_score,
            relative_threshold,
        )

        selected = [
            candidate
            for candidate in candidates
            if candidate.rerank_score >= threshold
        ]

        if (
            len(selected)
            < self.config.minimum_results
        ):
            selected = candidates[
                : self.config.minimum_results
            ]

        return selected[:limit]
