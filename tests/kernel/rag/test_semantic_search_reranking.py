from rkjo_kernel.rag.models import (
    DocumentChunk,
    RetrievedChunk,
)
from rkjo_kernel.rag.relevance_filter import (
    RelevanceFilter,
    RelevanceFilterConfig,
)
from rkjo_kernel.rag.reranker import (
    LexicalOverlapReranker,
)
from rkjo_kernel.rag.semantic_search import (
    SemanticSearchService,
)


class FakeSanitizer:
    class Result:
        def __init__(self, content):
            self.content = content

    def sanitize(self, content):
        return self.Result(content)


class RecordingRetriever:
    def __init__(self):
        self.limits = []

    def retrieve(
        self,
        query,
        *,
        limit=5,
    ):
        self.limits.append(limit)

        return [
            RetrievedChunk(
                chunk=DocumentChunk(
                    document_id="generic",
                    chunk_id="generic-1",
                    content=(
                        "Informations agricoles "
                        "générales."
                    ),
                    chunk_index=0,
                ),
                score=0.95,
            ),
            RetrievedChunk(
                chunk=DocumentChunk(
                    document_id="maize",
                    chunk_id="maize-1",
                    content=(
                        "La sécheresse réduit "
                        "le rendement du maïs."
                    ),
                    chunk_index=0,
                ),
                score=0.60,
            ),
            RetrievedChunk(
                chunk=DocumentChunk(
                    document_id="football",
                    chunk_id="football-1",
                    content=(
                        "Le championnat de football."
                    ),
                    chunk_index=0,
                ),
                score=0.80,
            ),
        ]


def build_service(retriever):
    return SemanticSearchService(
        retriever=retriever,
        sanitizer=FakeSanitizer(),
        reranker=(
            LexicalOverlapReranker()
        ),
        relevance_filter=(
            RelevanceFilter(
                RelevanceFilterConfig(
                    minimum_score=0.20,
                    relative_to_top=0.50,
                )
            )
        ),
        candidate_multiplier=4,
    )


def test_search_fetches_more_candidates():
    retriever = RecordingRetriever()

    service = build_service(retriever)

    service.search(
        "sécheresse rendement maïs",
        limit=1,
    )

    assert retriever.limits == [4]


def test_search_filters_distractors_after_reranking():
    retriever = RecordingRetriever()

    result = build_service(
        retriever
    ).search(
        "sécheresse rendement maïs",
        limit=5,
    )

    assert result.result_count == 1

    assert (
        result.results[0].document_id
        == "maize"
    )


def test_candidate_limit_is_derived_from_multiplier():
    retriever = RecordingRetriever()

    service = build_service(retriever)

    service.search(
        "sécheresse",
        limit=20,
    )

    assert retriever.limits == [80]
