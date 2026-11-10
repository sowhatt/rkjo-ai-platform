"""Page citations on multimodal evidence RAG answers."""
from rkjo_kernel.rag.context_builder import CitationContextBuilder
from rkjo_kernel.rag.rag_answering import RAGAnsweringService
from rkjo_kernel.rag.semantic_search import SemanticSearchResponse, SemanticSearchResult


class Search:
    def search(self, question, *, limit=5):
        results = [SemanticSearchResult(
            chunk_id="chunk-ocr", document_id="policy",
            content="Garantie optique 250 euros.", score=0.95,
            metadata={"tenant_id": "tenant-a", "page_number": 4},
        )]
        return SemanticSearchResponse(
            sanitized_query=question, result_count=1, results=results,
        )


class Generator:
    def __init__(self):
        self.context = None

    def generate(self, *, question, context):
        self.context = context
        return "Garantie optique : 250 euros [1]."


def test_answer_source_contains_document_page_and_context_citation():
    generator = Generator()
    result = RAGAnsweringService(
        search_service=Search(), generator=generator,
    ).answer("Garantie optique ?")
    assert result.sources[0].document_id == "policy"
    assert result.sources[0].page_number == 4
    assert "page_number: 4" in generator.context
    assert result.answer.endswith("[1].")


def test_legacy_source_without_page_is_unchanged():
    no_page = SemanticSearchResult(
        chunk_id="old", document_id="legacy", content="Historique",
        score=0.9, metadata={},
    )
    context = CitationContextBuilder().build([no_page])
    assert "page_number:" not in context.content
