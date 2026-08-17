"""Retrieval-only benchmark for RKJO hybrid search."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationCase:
    case_id: str
    query: str
    expected_document_id: str
    limit: int = 5

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError(
                "case_id must not be empty."
            )

        if not self.query.strip():
            raise ValueError(
                "query must not be empty."
            )

        if not self.expected_document_id.strip():
            raise ValueError(
                "expected_document_id must not be empty."
            )

        if not 1 <= self.limit <= 20:
            raise ValueError(
                "limit must be between 1 and 20."
            )


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationCaseResult:
    case_id: str
    expected_document_id: str
    retrieved_document_ids: tuple[str, ...]
    expected_rank: int | None
    hit_at_1: bool
    recall_at_k: float
    reciprocal_rank: float
    latency_ms: int


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationReport:
    case_count: int
    hit_at_1: float
    recall_at_k: float
    mean_reciprocal_rank: float
    mean_latency_ms: float
    cases: list[RetrievalEvaluationCaseResult]


class RetrievalEvaluationHarness:
    """Evaluate SemanticSearchService without calling an LLM."""

    def __init__(
        self,
        *,
        search_service,
    ) -> None:
        self.search_service = search_service

    def evaluate_case(
        self,
        case: RetrievalEvaluationCase,
    ) -> RetrievalEvaluationCaseResult:
        started = perf_counter()

        response = self.search_service.search(
            case.query,
            limit=case.limit,
        )

        latency_ms = int(
            (
                perf_counter()
                - started
            )
            * 1000
        )

        document_ids = tuple(
            result.document_id
            for result in response.results
        )

        expected_rank = None

        for index, document_id in enumerate(
            document_ids,
            start=1,
        ):
            if (
                document_id
                == case.expected_document_id
            ):
                expected_rank = index
                break

        return RetrievalEvaluationCaseResult(
            case_id=case.case_id,
            expected_document_id=(
                case.expected_document_id
            ),
            retrieved_document_ids=document_ids,
            expected_rank=expected_rank,
            hit_at_1=expected_rank == 1,
            recall_at_k=(
                1.0
                if expected_rank is not None
                else 0.0
            ),
            reciprocal_rank=(
                1.0 / expected_rank
                if expected_rank is not None
                else 0.0
            ),
            latency_ms=latency_ms,
        )

    def evaluate(
        self,
        cases: list[RetrievalEvaluationCase],
    ) -> RetrievalEvaluationReport:
        if not cases:
            raise ValueError(
                "Retrieval evaluation dataset "
                "must not be empty."
            )

        results = [
            self.evaluate_case(case)
            for case in cases
        ]

        count = len(results)

        return RetrievalEvaluationReport(
            case_count=count,
            hit_at_1=(
                sum(
                    int(result.hit_at_1)
                    for result in results
                )
                / count
            ),
            recall_at_k=(
                sum(
                    result.recall_at_k
                    for result in results
                )
                / count
            ),
            mean_reciprocal_rank=(
                sum(
                    result.reciprocal_rank
                    for result in results
                )
                / count
            ),
            mean_latency_ms=(
                sum(
                    result.latency_ms
                    for result in results
                )
                / count
            ),
            cases=results,
        )
