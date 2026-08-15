"""RAG observability and structural evaluation primitives."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass

from rkjo_kernel.logging.structured import (
    structured_log,
)
from rkjo_kernel.monitoring.metrics import (
    MetricsRegistry,
)
from rkjo_kernel.rag.generation_models import (
    RAGAnswer,
)


@dataclass(frozen=True, slots=True)
class RAGTiming:
    retrieval_ms: int
    generation_ms: int
    total_ms: int


@dataclass(frozen=True, slots=True)
class RAGEvaluation:
    source_count: int
    citation_count: int
    citation_coverage: float
    has_sources: bool
    has_citations: bool


class RAGObserver:
    """Record privacy-safe RAG metrics and structured events."""

    def __init__(
        self,
        *,
        metrics: MetricsRegistry,
        logger: logging.Logger,
    ) -> None:
        self.metrics = metrics
        self.logger = logger

    def record_answer(
        self,
        *,
        sanitized_query: str,
        answer: RAGAnswer,
        timing: RAGTiming,
        retrieval_result_count: int,
        top_score: float | None,
    ) -> RAGEvaluation:
        evaluation = evaluate_rag_answer(
            answer
        )

        self.metrics.increment(
            "rag.answers.total"
        )

        self.metrics.increment(
            "rag.retrieval.total_ms",
            timing.retrieval_ms,
        )

        self.metrics.increment(
            "rag.generation.total_ms",
            timing.generation_ms,
        )

        self.metrics.increment(
            "rag.total.total_ms",
            timing.total_ms,
        )

        self.metrics.increment(
            "rag.sources.total",
            evaluation.source_count,
        )

        if evaluation.has_sources:
            self.metrics.increment(
                "rag.answers.with_sources"
            )
        else:
            self.metrics.increment(
                "rag.answers.insufficient_context"
            )

        if evaluation.has_citations:
            self.metrics.increment(
                "rag.answers.with_citations"
            )

        structured_log(
            self.logger,
            event="rag.answer.completed",
            query_hash=query_fingerprint(
                sanitized_query
            ),
            retrieval_ms=timing.retrieval_ms,
            generation_ms=timing.generation_ms,
            total_ms=timing.total_ms,
            retrieval_result_count=(
                retrieval_result_count
            ),
            source_count=evaluation.source_count,
            citation_count=(
                evaluation.citation_count
            ),
            citation_coverage=(
                evaluation.citation_coverage
            ),
            top_score=top_score,
        )

        return evaluation


def query_fingerprint(
    query: str,
) -> str:
    """Hash a sanitized query instead of logging its content."""

    return hashlib.sha256(
        query.encode("utf-8")
    ).hexdigest()[:16]


def evaluate_rag_answer(
    answer: RAGAnswer,
) -> RAGEvaluation:
    citations = {
        int(value)
        for value in re.findall(
            r"\[(\d+)\]",
            answer.answer,
        )
    }

    source_numbers = {
        source.citation
        for source in answer.sources
    }

    valid_citations = (
        citations
        & source_numbers
    )

    source_count = len(
        answer.sources
    )

    citation_count = len(
        valid_citations
    )

    coverage = (
        citation_count / source_count
        if source_count
        else 0.0
    )

    return RAGEvaluation(
        source_count=source_count,
        citation_count=citation_count,
        citation_coverage=coverage,
        has_sources=source_count > 0,
        has_citations=citation_count > 0,
    )
