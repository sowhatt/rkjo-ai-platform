from rkjo_kernel.rag.rag_answering import (
    RAGAnsweringService,
)
from rkjo_kernel.rag.semantic_search import (
    SemanticSearchResponse,
    SemanticSearchResult,
)


class FakeSearch:
    def __init__(self, results):
        self.results = results

    def search(self, query, *, limit=5):
        return SemanticSearchResponse(
            sanitized_query=query.replace(
                "jean@example.com",
                "[EMAIL]",
            ),
            result_count=len(self.results),
            results=self.results,
        )


class FakeGenerator:
    def __init__(self):
        self.calls = []

    def generate(
        self,
        *,
        question,
        context,
    ):
        self.calls.append(
            (question, context)
        )
        return (
            "La sécheresse peut réduire "
            "le rendement du maïs [1]."
        )


def source():
    return SemanticSearchResult(
        chunk_id="chunk-1",
        document_id="doc-1",
        content=(
            "Une sécheresse prolongée peut "
            "réduire le rendement du maïs."
        ),
        score=0.9,
        metadata={},
    )


def test_answer_uses_sanitized_query_and_sources():
    generator = FakeGenerator()

    service = RAGAnsweringService(
        search_service=FakeSearch(
            [source()]
        ),
        generator=generator,
    )

    result = service.answer(
        "Que dit jean@example.com sur le maïs ?"
    )

    assert (
        result.sanitized_query
        == "Que dit [EMAIL] sur le maïs ?"
    )

    assert len(result.sources) == 1
    assert result.sources[0].citation == 1
    assert (
        result.sources[0].document_id
        == "doc-1"
    )

    question, context = generator.calls[0]

    assert "jean@example.com" not in question
    assert "[EMAIL]" in question
    assert "[1]" in context


def test_no_sources_does_not_call_generator():
    generator = FakeGenerator()

    service = RAGAnsweringService(
        search_service=FakeSearch([]),
        generator=generator,
    )

    result = service.answer(
        "Question sans source"
    )

    assert result.sources == []
    assert generator.calls == []
    assert (
        "do not provide enough information"
        in result.answer
    )
