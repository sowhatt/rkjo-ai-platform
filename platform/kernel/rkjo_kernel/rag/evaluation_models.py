"""Deterministic RAG evaluation domain models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RAGEvaluationCase:
    case_id: str
    question: str
    expected_document_ids: tuple[str, ...] = ()
    expected_concepts: tuple[str, ...] = ()
    expect_answerable: bool = True
    limit: int = 5

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError(
                "Evaluation case_id must not be empty."
            )

        if not self.question.strip():
            raise ValueError(
                "Evaluation question must not be empty."
            )

        if not 1 <= self.limit <= 20:
            raise ValueError(
                "Evaluation limit must be between 1 and 20."
            )


@dataclass(frozen=True, slots=True)
class RAGEvaluationCaseResult:
    case_id: str
    retrieval_hit: bool
    recall_at_k: float
    concept_coverage: float
    citation_coverage: float
    citation_validity: float
    answerability_correct: bool
    retrieved_document_ids: tuple[str, ...]
    missing_concepts: tuple[str, ...]
    total_ms: int


@dataclass(frozen=True, slots=True)
class RAGEvaluationReport:
    case_count: int
    retrieval_hit_rate: float
    mean_recall_at_k: float
    mean_concept_coverage: float
    mean_citation_coverage: float
    mean_citation_validity: float
    answerability_accuracy: float
    mean_total_ms: float
    cases: list[RAGEvaluationCaseResult] = field(
        default_factory=list
    )
