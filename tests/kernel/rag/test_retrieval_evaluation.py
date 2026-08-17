import pytest

from rkjo_kernel.rag.retrieval_evaluation import (
    RetrievalEvaluationCase,
    RetrievalEvaluationHarness,
)
from rkjo_kernel.rag.semantic_search import (
    SemanticSearchResponse,
    SemanticSearchResult,
)


def result(document_id):
    return SemanticSearchResult(
        chunk_id=f"{document_id}-chunk",
        document_id=document_id,
        content=document_id,
        score=0.5,
        metadata={},
    )


class FakeSearch:
    def __init__(self, results):
        self.results = results

    def search(
        self,
        query,
        *,
        limit=5,
    ):
        return SemanticSearchResponse(
            sanitized_query=query,
            result_count=len(
                self.results[:limit]
            ),
            results=self.results[:limit],
        )


def test_expected_document_at_rank_one():
    harness = RetrievalEvaluationHarness(
        search_service=FakeSearch(
            [
                result("expected"),
                result("other"),
            ]
        )
    )

    outcome = harness.evaluate_case(
        RetrievalEvaluationCase(
            case_id="one",
            query="REF",
            expected_document_id="expected",
        )
    )

    assert outcome.hit_at_1 is True
    assert outcome.expected_rank == 1
    assert outcome.reciprocal_rank == 1.0
    assert outcome.recall_at_k == 1.0


def test_rank_three_changes_mrr():
    harness = RetrievalEvaluationHarness(
        search_service=FakeSearch(
            [
                result("a"),
                result("b"),
                result("expected"),
            ]
        )
    )

    outcome = harness.evaluate_case(
        RetrievalEvaluationCase(
            case_id="three",
            query="REF",
            expected_document_id="expected",
        )
    )

    assert outcome.hit_at_1 is False
    assert outcome.expected_rank == 3
    assert outcome.reciprocal_rank == pytest.approx(
        1 / 3
    )


def test_missing_document_scores_zero():
    outcome = RetrievalEvaluationHarness(
        search_service=FakeSearch(
            [result("other")]
        )
    ).evaluate_case(
        RetrievalEvaluationCase(
            case_id="missing",
            query="REF",
            expected_document_id="expected",
        )
    )

    assert outcome.expected_rank is None
    assert outcome.hit_at_1 is False
    assert outcome.recall_at_k == 0.0
    assert outcome.reciprocal_rank == 0.0


def test_report_aggregates_hit_and_mrr():
    harness = RetrievalEvaluationHarness(
        search_service=FakeSearch(
            [
                result("expected"),
            ]
        )
    )

    report = harness.evaluate(
        [
            RetrievalEvaluationCase(
                case_id="a",
                query="A",
                expected_document_id="expected",
            ),
            RetrievalEvaluationCase(
                case_id="b",
                query="B",
                expected_document_id="expected",
            ),
        ]
    )

    assert report.case_count == 2
    assert report.hit_at_1 == 1.0
    assert report.recall_at_k == 1.0
    assert (
        report.mean_reciprocal_rank
        == 1.0
    )


def test_empty_dataset_rejected():
    harness = RetrievalEvaluationHarness(
        search_service=FakeSearch([])
    )

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        harness.evaluate([])
