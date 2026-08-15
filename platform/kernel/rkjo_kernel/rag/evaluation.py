"""Deterministic evaluation harness for RKJO RAG."""

from __future__ import annotations

import re
from time import perf_counter

from rkjo_kernel.rag.evaluation_models import (
    RAGEvaluationCase,
    RAGEvaluationCaseResult,
    RAGEvaluationReport,
)
from rkjo_kernel.rag.observability import (
    evaluate_rag_answer,
)
from rkjo_kernel.rag.rag_answering import (
    RAGAnsweringService,
)


INSUFFICIENT_CONTEXT_MARKERS = (
    "do not provide enough information",
    "not enough information",
    "insufficient information",
    "pas assez d'information",
    "pas suffisamment d'information",
    "sources disponibles ne fournissent pas",
)


class RAGEvaluationHarness:
    """Evaluate a RAG service using deterministic expectations."""

    def __init__(
        self,
        *,
        service: RAGAnsweringService,
    ) -> None:
        self.service = service

    def evaluate_case(
        self,
        case: RAGEvaluationCase,
    ) -> RAGEvaluationCaseResult:
        started = perf_counter()

        answer = self.service.answer(
            case.question,
            limit=case.limit,
        )

        total_ms = int(
            (
                perf_counter()
                - started
            )
            * 1000
        )

        retrieved_document_ids = tuple(
            dict.fromkeys(
                source.document_id
                for source in answer.sources
            )
        )

        expected_documents = set(
            case.expected_document_ids
        )

        retrieved_documents = set(
            retrieved_document_ids
        )

        if expected_documents:
            matched_documents = (
                expected_documents
                & retrieved_documents
            )

            recall_at_k = (
                len(matched_documents)
                / len(expected_documents)
            )

            retrieval_hit = bool(
                matched_documents
            )
        else:
            recall_at_k = 1.0
            retrieval_hit = True

        normalized_answer = (
            answer.answer.casefold()
        )

        concepts = tuple(
            concept
            for concept in case.expected_concepts
            if concept.strip()
        )

        missing_concepts = tuple(
            concept
            for concept in concepts
            if concept.casefold()
            not in normalized_answer
        )

        concept_coverage = (
            (
                len(concepts)
                - len(missing_concepts)
            )
            / len(concepts)
            if concepts
            else 1.0
        )

        structural = evaluate_rag_answer(
            answer
        )

        citation_validity = (
            _citation_validity(
                answer.answer,
                valid_citations={
                    source.citation
                    for source in answer.sources
                },
            )
        )

        insufficient = (
            _looks_insufficient(
                answer.answer
            )
            or not answer.sources
        )

        answerability_correct = (
            (
                case.expect_answerable
                and not insufficient
            )
            or (
                not case.expect_answerable
                and insufficient
            )
        )

        return RAGEvaluationCaseResult(
            case_id=case.case_id,
            retrieval_hit=retrieval_hit,
            recall_at_k=recall_at_k,
            concept_coverage=concept_coverage,
            citation_coverage=(
                structural.citation_coverage
            ),
            citation_validity=(
                citation_validity
            ),
            answerability_correct=(
                answerability_correct
            ),
            retrieved_document_ids=(
                retrieved_document_ids
            ),
            missing_concepts=(
                missing_concepts
            ),
            total_ms=total_ms,
        )

    def evaluate(
        self,
        cases: list[RAGEvaluationCase],
    ) -> RAGEvaluationReport:
        if not cases:
            raise ValueError(
                "Evaluation dataset must not be empty."
            )

        results = [
            self.evaluate_case(case)
            for case in cases
        ]

        count = len(results)

        return RAGEvaluationReport(
            case_count=count,
            retrieval_hit_rate=(
                sum(
                    int(result.retrieval_hit)
                    for result in results
                )
                / count
            ),
            mean_recall_at_k=(
                sum(
                    result.recall_at_k
                    for result in results
                )
                / count
            ),
            mean_concept_coverage=(
                sum(
                    result.concept_coverage
                    for result in results
                )
                / count
            ),
            mean_citation_coverage=(
                sum(
                    result.citation_coverage
                    for result in results
                )
                / count
            ),
            mean_citation_validity=(
                sum(
                    result.citation_validity
                    for result in results
                )
                / count
            ),
            answerability_accuracy=(
                sum(
                    int(
                        result.answerability_correct
                    )
                    for result in results
                )
                / count
            ),
            mean_total_ms=(
                sum(
                    result.total_ms
                    for result in results
                )
                / count
            ),
            cases=results,
        )


def _citation_validity(
    answer: str,
    *,
    valid_citations: set[int],
) -> float:
    citations = [
        int(value)
        for value in re.findall(
            r"\[(\d+)\]",
            answer,
        )
    ]

    if not citations:
        return (
            1.0
            if not valid_citations
            else 0.0
        )

    valid = sum(
        citation in valid_citations
        for citation in citations
    )

    return valid / len(citations)


def _looks_insufficient(
    answer: str,
) -> bool:
    normalized = answer.casefold()

    return any(
        marker in normalized
        for marker in (
            INSUFFICIENT_CONTEXT_MARKERS
        )
    )
