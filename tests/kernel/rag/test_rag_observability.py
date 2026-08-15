import logging

from rkjo_kernel.monitoring.metrics import (
    MetricsRegistry,
)
from rkjo_kernel.rag.generation_models import (
    AnswerSource,
    RAGAnswer,
)
from rkjo_kernel.rag.observability import (
    RAGObserver,
    RAGTiming,
    evaluate_rag_answer,
    query_fingerprint,
)


def answer_with_source():
    return RAGAnswer(
        answer=(
            "La sécheresse réduit "
            "le rendement [1]."
        ),
        sanitized_query="sécheresse maïs",
        sources=[
            AnswerSource(
                citation=1,
                document_id="doc-1",
                chunk_id="chunk-1",
                score=0.8,
            )
        ],
    )


def test_query_fingerprint_is_stable_and_private():
    first = query_fingerprint(
        "question sanitized"
    )

    second = query_fingerprint(
        "question sanitized"
    )

    assert first == second
    assert (
        "question sanitized"
        not in first
    )


def test_structural_evaluation_detects_citation_coverage():
    evaluation = evaluate_rag_answer(
        answer_with_source()
    )

    assert evaluation.source_count == 1
    assert evaluation.citation_count == 1
    assert evaluation.citation_coverage == 1.0
    assert evaluation.has_sources is True
    assert evaluation.has_citations is True


def test_observer_records_metrics():
    metrics = MetricsRegistry()

    logger = logging.getLogger(
        "test.rag.observer"
    )

    observer = RAGObserver(
        metrics=metrics,
        logger=logger,
    )

    observer.record_answer(
        sanitized_query="question",
        answer=answer_with_source(),
        timing=RAGTiming(
            retrieval_ms=10,
            generation_ms=20,
            total_ms=35,
        ),
        retrieval_result_count=1,
        top_score=0.8,
    )

    assert metrics.get(
        "rag.answers.total"
    ) == 1

    assert metrics.get(
        "rag.answers.with_sources"
    ) == 1

    assert metrics.get(
        "rag.answers.with_citations"
    ) == 1

    assert metrics.get(
        "rag.retrieval.total_ms"
    ) == 10

    assert metrics.get(
        "rag.generation.total_ms"
    ) == 20

    assert metrics.get(
        "rag.total.total_ms"
    ) == 35


def test_observer_records_insufficient_context():
    metrics = MetricsRegistry()

    observer = RAGObserver(
        metrics=metrics,
        logger=logging.getLogger(
            "test.rag.empty"
        ),
    )

    answer = RAGAnswer(
        answer=(
            "The available sources do not "
            "provide enough information."
        ),
        sanitized_query="unknown",
        sources=[],
    )

    observer.record_answer(
        sanitized_query="unknown",
        answer=answer,
        timing=RAGTiming(
            retrieval_ms=5,
            generation_ms=0,
            total_ms=5,
        ),
        retrieval_result_count=0,
        top_score=None,
    )

    assert metrics.get(
        "rag.answers.insufficient_context"
    ) == 1
