"""Shared, configured retrieval factory for API and platform workers."""
import os
from rkjo_kernel.rag.chunking import TextChunker
from rkjo_kernel.rag.embedding_factory import build_embedding_provider, get_embedding_dimensions, get_embedding_space
from rkjo_kernel.rag.postgres_vector_store import PostgresPgVectorStore
from rkjo_kernel.rag.privacy import RuleBasedPIISanitizer, SanitizationMode
from rkjo_kernel.rag.retriever import Retriever
from rkjo_kernel.rag.hybrid_retriever import HybridRetriever, ReciprocalRankFusion
from rkjo_kernel.rag.postgres_lexical_retriever import PostgresLexicalRetriever
from rkjo_kernel.rag.retrieval_factory import get_retrieval_mode, get_rrf_k
from rkjo_kernel.rag.reranking_factory import build_relevance_filter, build_reranker, get_reranking_candidate_multiplier
from rkjo_kernel.rag.semantic_search import SemanticSearchService

def build_search_service(*, database_url=None) -> SemanticSearchService:
    """Build the production privacy-aware RAG search service."""

    database_url = database_url or os.environ["RKJO_DATABASE_URL"]
    dimensions = get_embedding_dimensions()

    vector_store = PostgresPgVectorStore(
        database_url=database_url,
        dimensions=dimensions,
        table_name="rag_chunks",
        embedding_space=get_embedding_space(),
    )

    vector_store.initialize_schema()

    vector_retriever = Retriever(
        chunker=TextChunker(
            chunk_size=1000,
            overlap=150,
        ),
        embedding_provider=(
            build_embedding_provider()
        ),
        vector_store=vector_store,
    )

    retrieval_mode = (
        get_retrieval_mode()
    )

    if retrieval_mode == "hybrid":
        lexical_retriever = (
            PostgresLexicalRetriever(
                database_url=database_url,
                table_name="rag_chunks",
                embedding_space=(
                    get_embedding_space()
                ),
            )
        )

        lexical_retriever.initialize_schema()

        retriever = HybridRetriever(
            vector_retriever=(
                vector_retriever
            ),
            lexical_retriever=(
                lexical_retriever
            ),
            fusion=ReciprocalRankFusion(
                k=get_rrf_k()
            ),
        )

    else:
        retriever = vector_retriever

    return SemanticSearchService(
        retriever=retriever,
        sanitizer=RuleBasedPIISanitizer(
            mode=SanitizationMode.REDACT
        ),
        reranker=build_reranker(),
        relevance_filter=(
            build_relevance_filter()
        ),
        candidate_multiplier=(
            get_reranking_candidate_multiplier()
        ),
    )
