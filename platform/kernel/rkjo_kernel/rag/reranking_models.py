"""Models used by the RAG reranking stage."""

from __future__ import annotations

from dataclasses import dataclass

from rkjo_kernel.rag.models import RetrievedChunk


@dataclass(frozen=True, slots=True)
class RerankedChunk:
    """Candidate enriched with a reranking score."""

    retrieved: RetrievedChunk
    rerank_score: float

    @property
    def vector_score(self) -> float:
        return self.retrieved.score
