from rkjo_kernel.rag.generation_models import (
    RAGAnswer,
)
from rkjo_kernel.rag.rag_answering import (
    RAGAnsweringService,
)
from rkjo_kernel.rag.retrieval_filters import (
    RetrievalFilters,
)
from rkjo_kernel.rag.semantic_search import (
    SemanticSearchResponse,
)


class RecordingSearchService:
    def __init__(self):
        self.calls = []

    def search(
        self,
        query,
        *,
        limit=5,
        filters=None,
    ):
        self.calls.append(
            (
                query,
                limit,
                filters,
            )
        )

        return SemanticSearchResponse(
            sanitized_query=query,
            result_count=0,
            results=[],
        )


class NeverCalledGenerator:
    def generate(
        self,
        *,
        question,
        context,
    ):
        raise AssertionError(
            "Generator must not be called "
            "without retrieval results."
        )


def test_answer_propagates_metadata_filters():
    search = RecordingSearchService()

    service = RAGAnsweringService(
        search_service=search,
        generator=NeverCalledGenerator(),
    )

    filters = RetrievalFilters(
        metadata={
            "country": "benin",
            "domain": "agriculture",
        }
    )

    result = service.answer(
        "Question",
        limit=3,
        filters=filters,
    )

    assert isinstance(
        result,
        RAGAnswer,
    )

    assert search.calls == [
        (
            "Question",
            3,
            filters,
        )
    ]
