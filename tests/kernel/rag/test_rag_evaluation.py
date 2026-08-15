import pytest

from rkjo_kernel.rag.evaluation import (
    RAGEvaluationHarness,
)
from rkjo_kernel.rag.evaluation_models import (
    RAGEvaluationCase,
)
from rkjo_kernel.rag.generation_models import (
    AnswerSource,
    RAGAnswer,
)


class FakeService:
    def __init__(
        self,
        answer,
    ):
        self.answer_value = answer
        self.calls = []

    def answer(
        self,
        question,
        *,
        limit=5,
    ):
        self.calls.append(
            (question, limit)
        )

        return self.answer_value


def grounded_answer():
    return RAGAnswer(
        answer=(
            "La sécheresse et le manque "
            "d'eau réduisent le rendement [1]."
        ),
        sanitized_query="question",
        sources=[
            AnswerSource(
                citation=1,
                document_id="doc-1",
                chunk_id="chunk-1",
                score=0.9,
            )
        ],
    )


def test_case_measures_retrieval_and_concepts():
    harness = RAGEvaluationHarness(
        service=FakeService(
            grounded_answer()
        )
    )

    result = harness.evaluate_case(
        RAGEvaluationCase(
            case_id="case-1",
            question="question",
            expected_document_ids=(
                "doc-1",
            ),
            expected_concepts=(
                "sécheresse",
                "eau",
            ),
        )
    )

    assert result.retrieval_hit is True
    assert result.recall_at_k == 1.0
    assert result.concept_coverage == 1.0
    assert result.citation_coverage == 1.0
    assert result.citation_validity == 1.0
    assert (
        result.answerability_correct
        is True
    )


def test_missing_expected_document_reduces_recall():
    harness = RAGEvaluationHarness(
        service=FakeService(
            grounded_answer()
        )
    )

    result = harness.evaluate_case(
        RAGEvaluationCase(
            case_id="case-2",
            question="question",
            expected_document_ids=(
                "doc-2",
            ),
        )
    )

    assert result.retrieval_hit is False
    assert result.recall_at_k == 0.0


def test_invalid_citation_is_detected():
    answer = RAGAnswer(
        answer="Réponse inventée [9].",
        sanitized_query="question",
        sources=[
            AnswerSource(
                citation=1,
                document_id="doc-1",
                chunk_id="chunk-1",
                score=0.5,
            )
        ],
    )

    result = RAGEvaluationHarness(
        service=FakeService(answer)
    ).evaluate_case(
        RAGEvaluationCase(
            case_id="case-3",
            question="question",
        )
    )

    assert result.citation_validity == 0.0


def test_unanswerable_case_is_correct():
    answer = RAGAnswer(
        answer=(
            "The available sources do not "
            "provide enough information."
        ),
        sanitized_query="unknown",
        sources=[],
    )

    result = RAGEvaluationHarness(
        service=FakeService(answer)
    ).evaluate_case(
        RAGEvaluationCase(
            case_id="case-4",
            question="unknown",
            expect_answerable=False,
        )
    )

    assert (
        result.answerability_correct
        is True
    )


def test_report_aggregates_cases():
    harness = RAGEvaluationHarness(
        service=FakeService(
            grounded_answer()
        )
    )

    report = harness.evaluate(
        [
            RAGEvaluationCase(
                case_id="a",
                question="a",
                expected_document_ids=(
                    "doc-1",
                ),
            ),
            RAGEvaluationCase(
                case_id="b",
                question="b",
                expected_document_ids=(
                    "doc-1",
                ),
            ),
        ]
    )

    assert report.case_count == 2
    assert report.retrieval_hit_rate == 1.0
    assert report.mean_recall_at_k == 1.0
    assert report.mean_citation_coverage == 1.0
    assert report.mean_citation_validity == 1.0
    assert (
        report.answerability_accuracy
        == 1.0
    )


def test_empty_dataset_is_rejected():
    harness = RAGEvaluationHarness(
        service=FakeService(
            grounded_answer()
        )
    )

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        harness.evaluate([])
