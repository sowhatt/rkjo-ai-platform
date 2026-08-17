"""Grounded RAG answering orchestration."""

from __future__ import annotations

from time import perf_counter

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
from rkjo_kernel.rag.retrieval_filters import (
    RetrievalFilters,
)
from rkjo_kernel.rag.observability import (
    RAGObserver,
    RAGTiming,
)


class RAGAnsweringService:
    def __init__(
        self,
        *,
        search_service: SemanticSearchService,
        generator: AnswerGenerator,
        context_builder: CitationContextBuilder | None = None,
        observer: RAGObserver | None = None,
    ) -> None:
        self.search_service = search_service
        self.generator = generator
        self.context_builder = (
            context_builder
            or CitationContextBuilder()
        )
        self.observer = observer

    def answer(
        self,
        question: str,
        *,
        limit: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RAGAnswer:
        if not question.strip():
            raise ValueError(
                "Question must not be empty."
            )

        total_started = perf_counter()

        retrieval_started = perf_counter()

        if filters is None:
            search = self.search_service.search(
                question,
                limit=limit,
            )
        else:
            search = self.search_service.search(
                question,
                limit=limit,
                filters=filters,
            )

        retrieval_ms = int(
            (
                perf_counter()
                - retrieval_started
            )
            * 1000
        )

        if not search.results:
            result = RAGAnswer(
                answer=(
                    "The available sources do not provide "
                    "enough information to answer this question."
                ),
                sanitized_query=search.sanitized_query,
                sources=[],
            )

            self._observe(
                result=result,
                retrieval_ms=retrieval_ms,
                generation_ms=0,
                total_started=total_started,
                retrieval_result_count=0,
                top_score=None,
            )

            return result

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

        generation_started = perf_counter()

        answer = self.generator.generate(
            question=search.sanitized_query,
            context=context.content,
        )

        generation_ms = int(
            (
                perf_counter()
                - generation_started
            )
            * 1000
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

        result = RAGAnswer(
            answer=answer,
            sanitized_query=search.sanitized_query,
            sources=sources,
        )

        self._observe(
            result=result,
            retrieval_ms=retrieval_ms,
            generation_ms=generation_ms,
            total_started=total_started,
            retrieval_result_count=len(
                search.results
            ),
            top_score=(
                search.results[0].score
                if search.results
                else None
            ),
        )

        return result

    def _observe(
        self,
        *,
        result: RAGAnswer,
        retrieval_ms: int,
        generation_ms: int,
        total_started: float,
        retrieval_result_count: int,
        top_score: float | None,
    ) -> None:
        if self.observer is None:
            return

        total_ms = int(
            (
                perf_counter()
                - total_started
            )
            * 1000
        )

        self.observer.record_answer(
            sanitized_query=(
                result.sanitized_query
            ),
            answer=result,
            timing=RAGTiming(
                retrieval_ms=retrieval_ms,
                generation_ms=generation_ms,
                total_ms=total_ms,
            ),
            retrieval_result_count=(
                retrieval_result_count
            ),
            top_score=top_score,
        )
