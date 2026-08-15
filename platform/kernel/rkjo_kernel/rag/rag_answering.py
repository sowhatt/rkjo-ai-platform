"""Grounded RAG answering orchestration."""

from __future__ import annotations

from rkjo_kernel.rag.context_builder import (
    CitationContextBuilder,
)
from rkjo_kernel.rag.generation_models import (
    AnswerGenerator,
    AnswerSource,
    RAGAnswer,
)
from rkjo_kernel.rag.semantic_search import (
    SemanticSearchService,
)


class RAGAnsweringService:
    def __init__(
        self,
        *,
        search_service: SemanticSearchService,
        generator: AnswerGenerator,
        context_builder: CitationContextBuilder | None = None,
    ) -> None:
        self.search_service = search_service
        self.generator = generator
        self.context_builder = (
            context_builder
            or CitationContextBuilder()
        )

    def answer(
        self,
        question: str,
        *,
        limit: int = 5,
    ) -> RAGAnswer:
        if not question.strip():
            raise ValueError(
                "Question must not be empty."
            )

        search = self.search_service.search(
            question,
            limit=limit,
        )

        if not search.results:
            return RAGAnswer(
                answer=(
                    "The available sources do not provide "
                    "enough information to answer this question."
                ),
                sanitized_query=search.sanitized_query,
                sources=[],
            )

        context = self.context_builder.build(
            search.results
        )

        if not context.results:
            return RAGAnswer(
                answer=(
                    "The available sources do not provide "
                    "enough information to answer this question."
                ),
                sanitized_query=search.sanitized_query,
                sources=[],
            )

        answer = self.generator.generate(
            question=search.sanitized_query,
            context=context.content,
        )

        sources = [
            AnswerSource(
                citation=index,
                document_id=result.document_id,
                chunk_id=result.chunk_id,
                score=result.score,
            )
            for index, result in enumerate(
                context.results,
                start=1,
            )
        ]

        return RAGAnswer(
            answer=answer,
            sanitized_query=search.sanitized_query,
            sources=sources,
        )
