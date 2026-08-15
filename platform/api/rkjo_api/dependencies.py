import os

from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
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
        repository=get_workflow_repository()
    )



def get_event_bus() -> RabbitMQEventBus:
    return RabbitMQEventBus()


def get_async_dispatcher() -> AsyncWorkflowDispatcher:
    return AsyncWorkflowDispatcher(
        event_bus=get_event_bus()
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
