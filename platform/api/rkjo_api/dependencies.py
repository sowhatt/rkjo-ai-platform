from fastapi import Request
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
from rkjo_kernel.rag.postgres_document_restore import (
    PostgresDocumentRestoreRepository,
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
from rkjo_kernel.rag.rag_answering import RAGAnsweringService
from rkjo_kernel.rag.semantic_search import (
    SemanticSearchService,
)
from rkjo_kernel.monitoring.metrics import MetricsRegistry
from rkjo_kernel.registry.postgres_registry import (
    PostgresAgentRegistry,
)
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.workflow.agent_routing import WorkflowAgentRouter
from rkjo_kernel.workflow.async_dispatch import AsyncWorkflowDispatcher
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.postgres_unit_of_work import (
    PostgreSQLWorkflowUnitOfWork,
)
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


def get_workflow_uow_factory():
    """Build transactions that atomically persist workflow state and outbox."""
    database_url = get_database_url()

    def factory() -> PostgreSQLWorkflowUnitOfWork:
        return PostgreSQLWorkflowUnitOfWork(
            database_url
        )

    return factory



def get_event_bus() -> RabbitMQEventBus:
    return RabbitMQEventBus()


def get_async_dispatcher() -> AsyncWorkflowDispatcher:
    return AsyncWorkflowDispatcher(
        event_bus=None,
        metrics=get_metrics_registry(),
    )



def get_agent_registry() -> PostgresAgentRegistry:
    registry = PostgresAgentRegistry(
        get_database_url()
    )
    registry.initialize_schema()
    return registry


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


def get_rag_document_restore_repository(
) -> PostgresDocumentRestoreRepository:
    """Build production document restore repository."""

    database_url = get_database_url()

    version_repository = (
        PostgresDocumentVersionRepository(
            database_url=database_url,
            document_table_name="rag_documents",
            version_table_name="rag_document_versions",
            version_chunk_table_name=(
                "rag_document_version_chunks"
            ),
        )
    )

    version_repository.initialize_schema()

    return PostgresDocumentRestoreRepository(
        database_url=database_url,
        chunk_table_name="rag_chunks",
        hash_table_name="rag_document_hashes",
        document_table_name="rag_documents",
        version_table_name="rag_document_versions",
        version_chunk_table_name=(
            "rag_document_version_chunks"
        ),
        embedding_space=get_embedding_space(),
    )


def get_rag_search_service() -> SemanticSearchService:
    """Use the same configured retrieval composition as the platform worker."""
    from rkjo_kernel.rag.service_factory import build_search_service
    return build_search_service(database_url=get_database_url())


def get_rag_answering_service(http_request: Request):
    """Create resources only after route validation and tenant authorization."""
    from rkjo_api.identity import get_authenticated_identity
    from rkjo_kernel.composition import build_platform_kernel, build_answering_service
    from rkjo_kernel.mission.execution_context import ExecutionContext
    from rkjo_kernel.llm.gateway import LLMBudgetExceededError
    from rkjo_kernel.llm.router import LLMRoutingError
    from fastapi import HTTPException
    from uuid import uuid4

    class RequestAnsweringService:
        def answer(self, question, *, limit=5, filters=None):
            identity = get_authenticated_identity(http_request)
            if not identity.tenant_id:
                raise HTTPException(status_code=403, detail="Tenant-bound identity required.")
            kernel = None
            try:
                kernel = build_platform_kernel()
                kernel.start()
                service = build_answering_service(kernel, search_service=get_rag_search_service(),
                    observer=RAGObserver(metrics=get_metrics_registry(), logger=get_logger("rkjo.rag")))
                return service.answer(question, limit=limit, filters=filters,
                    execution_context=ExecutionContext(
                        mission_id=str(uuid4()), tenant_id=identity.tenant_id,
                        user_id=identity.subject, request_id=str(uuid4()),
                    ))
            except LLMBudgetExceededError as exc:
                raise HTTPException(status_code=429, detail="LLM budget unavailable.") from exc
            except (LLMRoutingError, RuntimeError) as exc:
                raise HTTPException(status_code=503, detail="Governed generation unavailable.") from exc
            finally:
                if kernel is not None:
                    kernel.stop()

    return RequestAnsweringService()


def get_education_course_service():
    from rkjo_education.course.postgres_repository import (
        PostgresCourseRepository,
    )
    from rkjo_education.course.service import (
        CourseService,
    )

    return CourseService(
        PostgresCourseRepository(
            get_database_url()
        )
    )


def get_education_curriculum_service():
    from rkjo_education.curriculum.postgres_repository import (
        PostgresCurriculumRepository,
    )
    from rkjo_education.curriculum.service import (
        CurriculumService,
    )

    return CurriculumService(
        PostgresCurriculumRepository(
            get_database_url()
        )
    )


def get_education_course_access():
    """Build course membership authorization on persistent PostgreSQL."""
    from rkjo_education.course.membership import (
        CourseAccess, PostgresCourseMembershipRepository,
    )
    repository = PostgresCourseMembershipRepository(get_database_url())
    repository.initialize_schema()
    return CourseAccess(repository)
