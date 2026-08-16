"""RAG reranking contracts and local implementations."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from rkjo_kernel.rag.models import RetrievedChunk
from rkjo_kernel.rag.reranking_models import (
    RerankedChunk,
)


class Reranker(ABC):
    """Score and reorder vector-retrieved candidates."""

    @abstractmethod
    def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
    ) -> list[RerankedChunk]:
        raise NotImplementedError


class NoOpReranker(Reranker):
    """Preserve vector ordering and expose vector score."""

    def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
    ) -> list[RerankedChunk]:
        _validate_query(query)

        return [
            RerankedChunk(
                retrieved=candidate,
                rerank_score=candidate.score,
            )
            for candidate in candidates
        ]


class LexicalOverlapReranker(Reranker):
    """Deterministic lexical reranker."""

    def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
    ) -> list[RerankedChunk]:
        _validate_query(query)

        query_terms = _meaningful_terms(query)

        scored = [
            RerankedChunk(
                retrieved=candidate,
                rerank_score=_lexical_score(
                    query_terms,
                    _meaningful_terms(
                        candidate.chunk.content
                    ),
                ),
            )
            for candidate in candidates
        ]

        return sorted(
            scored,
            key=lambda item: (
                item.rerank_score,
                item.vector_score,
            ),
            reverse=True,
        )


def _validate_query(query: str) -> None:
    if not query.strip():
        raise ValueError(
            "Reranking query must not be empty."
        )


def _lexical_score(
    query_terms: set[str],
    content_terms: set[str],
) -> float:
    if not query_terms:
        return 0.0

    return (
        len(query_terms & content_terms)
        / len(query_terms)
    )


def _meaningful_terms(text: str) -> set[str]:
    tokens = {
        token.casefold()
        for token in re.findall(
            r"\b\w{3,}\b",
            text,
            flags=re.UNICODE,
        )
    }

    return tokens - _STOP_WORDS


_STOP_WORDS = {
    "les",
    "des",
    "une",
    "dans",
    "avec",
    "pour",
    "sur",
    "que",
    "qui",
    "quel",
    "quelle",
    "quels",
    "quelles",
    "peut",
    "peuvent",
    "être",
    "est",
    "sont",
    "aux",
    "par",
    "plus",
    "moins",
    "comment",
    "pourquoi",
}
