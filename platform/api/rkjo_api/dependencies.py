import os

from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.rag.chunking import TextChunker
from rkjo_kernel.rag.embedding_factory import (
    build_embedding_provider,
    get_embedding_dimensions,
)
from rkjo_kernel.rag.ingestion import DocumentIngestionPipeline
from rkjo_kernel.rag.loaders import CompositeDocumentLoader
from rkjo_kernel.rag.postgres_deduplication import (
    PostgresDocumentHashRegistry,
)
from rkjo_kernel.rag.postgres_vector_store import (
    PostgresPgVectorStore,
)
from rkjo_kernel.rag.privacy import (
    RuleBasedPIISanitizer,
    SanitizationMode,
)
from rkjo_kernel.rag.retriever import Retriever
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
