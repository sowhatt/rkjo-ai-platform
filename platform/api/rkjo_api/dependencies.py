from rkjo_kernel.logging.logger import get_logger
from rkjo_kernel.rag.observability import RAGObserver
import os

from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.rag.chunking import TextChunker
from rkjo_kernel.rag.embedding_factory import (
    build_embedding_provider,
    get_embedding_dimensions,
    get_embedding_space,
)
from rkjo_kernel.rag.ingestion import DocumentIngestionPipeline
from rkjo_kernel.rag.document_lifecycle import (
    DocumentLifecycleService,
)
from rkjo_kernel.rag.document_replacement import (
    DocumentReplacementService,
)
from rkjo_kernel.rag.document_version_history import (
    DocumentVersionHistoryService,
)
from rkjo_kernel.rag.loaders import CompositeDocumentLoader
from rkjo_kernel.rag.postgres_deduplication import (
    PostgresDocumentHashRegistry,
)
from rkjo_kernel.rag.postgres_document_replacement import (
    PostgresDocumentReplacementRepository,
)
from rkjo_kernel.rag.postgres_document_versioning import (
    PostgresDocumentVersionRepository,
)
from rkjo_kernel.rag.postgres_vector_store import (
    PostgresPgVectorStore,
)
from rkjo_kernel.rag.privacy import (
    RuleBasedPIISanitizer,
    SanitizationMode,
)
from rkjo_kernel.rag.retriever import Retriever
from rkjo_kernel.rag.hybrid_retriever import (
    HybridRetriever,
    ReciprocalRankFusion,
)
from rkjo_kernel.rag.postgres_lexical_retriever import (
    PostgresLexicalRetriever,
)
from rkjo_kernel.rag.retrieval_factory import (
    get_retrieval_mode,
    get_rrf_k,
)
from rkjo_kernel.rag.reranking_factory import (
    build_relevance_filter,
    build_reranker,
    get_reranking_candidate_multiplier,
)

from rkjo_kernel.rag.context_builder import CitationContextBuilder
from rkjo_kernel.rag.openai_generation import OpenAIAnswerGenerator
from rkjo_kernel.rag.rag_answering import RAGAnsweringService
from rkjo_kernel.rag.semantic_search import (
    SemanticSearchService,
)
from rkjo_kernel.monitoring.metrics import MetricsRegistry
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.workflow.agent_routing import WorkflowAgentRouter
from rkjo_kernel.workflow.async_dispatch import AsyncWorkflowDispatcher
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.repository.postgres import (
    PostgreSQLWorkflowRepository,
)


def get_database_url() -> str:
    return os.getenv(
        "RKJO_DATABASE_URL",
        "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
    )


def get_workflow_repository() -> PostgreSQLWorkflowRepository:
    repository = PostgreSQLWorkflowRepository(
        get_database_url()
    )
    repository.initialize_schema()
    return repository


def get_workflow_engine() -> WorkflowEngine:
    return WorkflowEngine(
        repository=get_workflow_repository(),
        metrics=get_metrics_registry(),
    )



def get_event_bus() -> RabbitMQEventBus:
    return RabbitMQEventBus()


def get_async_dispatcher() -> AsyncWorkflowDispatcher:
    return AsyncWorkflowDispatcher(
        event_bus=get_event_bus(),
        metrics=get_metrics_registry(),
    )



def get_agent_registry() -> AgentRegistry:
    return AgentRegistry()


def get_registry_service() -> RegistryService:
    return RegistryService(
        registry=get_agent_registry()
    )


def get_workflow_agent_router() -> WorkflowAgentRouter:
    return WorkflowAgentRouter(
        registry_service=get_registry_service()
    )



_metrics_registry = MetricsRegistry()


def get_metrics_registry() -> MetricsRegistry:
    return _metrics_registry


def get_rag_ingestion_pipeline() -> DocumentIngestionPipeline:
    """Build the production RAG ingestion pipeline."""

    database_url = get_database_url()

    dimensions = get_embedding_dimensions()

    vector_store = PostgresPgVectorStore(
        database_url=database_url,
        dimensions=dimensions,
        table_name="rag_chunks",
        embedding_space=get_embedding_space(),
    )

    vector_store.initialize_schema()

    hash_registry = PostgresDocumentHashRegistry(
        database_url=database_url,
        table_name="rag_document_hashes",
    )

    hash_registry.initialize_schema()

    return DocumentIngestionPipeline(
        loader=CompositeDocumentLoader(),
        retriever=Retriever(
            chunker=TextChunker(
                chunk_size=1000,
                overlap=150,
            ),
            embedding_provider=(
                build_embedding_provider()
            ),
            vector_store=vector_store,
        ),
        hash_registry=hash_registry,
        sanitizer=RuleBasedPIISanitizer(
            mode=SanitizationMode.REDACT
        ),
    )





def get_rag_document_lifecycle_service(
) -> DocumentLifecycleService:
    """Build production RAG document lifecycle service."""

    database_url = get_database_url()
    dimensions = get_embedding_dimensions()

    vector_store = PostgresPgVectorStore(
        database_url=database_url,
        dimensions=dimensions,
        table_name="rag_chunks",
        embedding_space=get_embedding_space(),
    )

    vector_store.initialize_schema()

    hash_registry = PostgresDocumentHashRegistry(
        database_url=database_url,
        table_name="rag_document_hashes",
    )

    hash_registry.initialize_schema()

    return DocumentLifecycleService(
        vector_store=vector_store,
        hash_registry=hash_registry,
    )





def get_rag_document_replacement_service(
) -> DocumentReplacementService:
    """Build atomic production RAG replacement service."""

    database_url = get_database_url()

    version_repository = (
        PostgresDocumentVersionRepository(
            database_url=database_url,
            document_table_name="rag_documents",
            version_table_name=(
                "rag_document_versions"
            ),
            version_chunk_table_name=(
                "rag_document_version_chunks"
            ),
        )
    )

    version_repository.initialize_schema()

    return DocumentReplacementService(
        ingestion_pipeline=(
            get_rag_ingestion_pipeline()
        ),
        replacement_repository=(
            PostgresDocumentReplacementRepository(
                database_url=database_url,
                chunk_table_name="rag_chunks",
                hash_table_name=(
                    "rag_document_hashes"
                ),
                document_table_name=(
                    "rag_documents"
                ),
                version_table_name=(
                    "rag_document_versions"
                ),
                version_chunk_table_name=(
                    "rag_document_version_chunks"
                ),
                embedding_space=(
                    get_embedding_space()
                ),
            )
        ),
    )





def get_rag_document_version_history_service(
) -> DocumentVersionHistoryService:
    """Build production document version history service."""

    repository = (
        PostgresDocumentVersionRepository(
            database_url=get_database_url(),
            document_table_name=(
                "rag_documents"
            ),
            version_table_name=(
                "rag_document_versions"
            ),
            version_chunk_table_name=(
                "rag_document_version_chunks"
            ),
        )
    )

    repository.initialize_schema()

    return DocumentVersionHistoryService(
        repository=repository
    )


def get_rag_search_service() -> SemanticSearchService:
    """Build the production privacy-aware RAG search service."""

    database_url = get_database_url()
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


def get_rag_answering_service() -> RAGAnsweringService:
    """Build grounded production RAG answer generation."""

    api_key = os.getenv(
        "OPENAI_API_KEY",
        "",
    ).strip()

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required for RAG generation."
        )

    model = os.getenv(
        "RKJO_GENERATION_MODEL",
        "gpt-5-mini",
    ).strip()

    timeout_seconds = float(
        os.getenv(
            "RKJO_GENERATION_TIMEOUT_SECONDS",
            "20",
        )
    )

    max_retries = int(
        os.getenv(
            "RKJO_GENERATION_MAX_RETRIES",
            "2",
        )
    )

    max_context_characters = int(
        os.getenv(
            "RKJO_RAG_MAX_CONTEXT_CHARACTERS",
            "12000",
        )
    )

    return RAGAnsweringService(
        search_service=get_rag_search_service(),
        generator=OpenAIAnswerGenerator(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        ),
        context_builder=CitationContextBuilder(
            max_characters=max_context_characters,
        ),
        observer=RAGObserver(
            metrics=get_metrics_registry(),
            logger=get_logger(
                "rkjo.rag"
            ),
        ),
    )
