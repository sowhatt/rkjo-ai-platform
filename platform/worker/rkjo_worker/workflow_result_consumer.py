"""Production consumer for asynchronous workflow results."""

from __future__ import annotations

import os

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.registry.descriptor import AgentStatus
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.workflow.agent_routing import WorkflowAgentRouter
from rkjo_kernel.workflow.async_dispatch import AsyncWorkflowDispatcher
from rkjo_kernel.workflow.postgres_unit_of_work import (
    PostgreSQLWorkflowUnitOfWork,
)
from rkjo_kernel.workflow.transactional_result_handler import (
    TransactionalWorkflowResultHandler,
)
from rkjo_worker.agent_catalog import (
    register_platform_worker,
)


def get_env(
    name: str,
    default: str,
) -> str:
    value = os.getenv(
        name,
        default,
    ).strip()

    if not value:
        raise RuntimeError(
            f"{name} must not be empty."
        )

    return value


def build_result_handler(
    *,
    event_bus: EventBus,
) -> tuple[
    str,
    TransactionalWorkflowResultHandler,
]:
    """Build the production workflow result handler."""

    database_url = get_env(
        "RKJO_DATABASE_URL",
        "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
    )

    result_queue = get_env(
        "RKJO_WORKFLOW_RESULT_QUEUE",
        "rkjo.workflow.results",
    )

    registry = AgentRegistry()

    registry_service = RegistryService(
        registry=registry,
    )

    register_platform_worker(
        registry_service,
        status=AgentStatus.AVAILABLE,
    )

    router = WorkflowAgentRouter(
        registry_service=registry_service,
    )

    dispatcher = AsyncWorkflowDispatcher(
        event_bus=event_bus,
    )

    uow_factory = lambda: PostgreSQLWorkflowUnitOfWork(
        database_url
    )

    handler = TransactionalWorkflowResultHandler(
        uow_factory=uow_factory,
        router=router,
        dispatcher=dispatcher,
        reply_queue=result_queue,
    )

    return result_queue, handler


def main() -> None:
    event_bus = RabbitMQEventBus()

    result_queue, handler = build_result_handler(
        event_bus=event_bus,
    )

    try:
        event_bus.consume_agent_messages(
            queue_name=result_queue,
            callback=handler.handle,
        )
    finally:
        event_bus.close()


if __name__ == "__main__":
    main()
