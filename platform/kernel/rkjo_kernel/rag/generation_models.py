"""Domain models for grounded RAG answer generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AnswerSource:
    citation: int
    document_id: str
    chunk_id: str
    score: float


@dataclass(frozen=True, slots=True)
class RAGAnswer:
    answer: str
    sanitized_query: str
    sources: list[AnswerSource]


class AnswerGenerator(Protocol):
    """Generate an answer from an explicitly supplied context."""

    def generate(
        self,
        *,
        question: str,
        context: str,
    ) -> str:
        ...
