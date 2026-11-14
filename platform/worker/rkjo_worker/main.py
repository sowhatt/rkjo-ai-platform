"""Production worker bootstrap for RKJO AI Platform."""

from __future__ import annotations

import os
import signal
from threading import Event, Thread
from typing import Any
from uuid import uuid4

from rkjo_kernel.workflow.postgres_unit_of_work import PostgreSQLWorkflowUnitOfWork
from rkjo_kernel.workflow.security_authorization import WorkflowAuthorization, ResultAuthenticator
from rkjo_kernel.agents.base_agent import BaseAgent
from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_worker.agent_catalog import (
    build_platform_worker_descriptor,
)
from rkjo_worker.health_http import HealthHTTPServer
from rkjo_worker.runtime_health import RuntimeHealthAdapter
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.registry.postgres_registry import (
    PostgresAgentRegistry,
)
from rkjo_kernel.runtime.agent_runtime import AgentRuntime
from rkjo_kernel.runtime.result_publisher import AgentResultPublisher
from rkjo_kernel.services.registry_service import RegistryService


class PlatformWorkerAgent(BaseAgent):
    """Minimal production worker used to validate distributed runtime."""

    def process(
        self,
        message: AgentMessage,
    ) -> Any:
        return {
            "processed_by": self.agent_name,
            "message_id": message.message_id,
            "payload": message.payload,
        }


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


def build_runtime(
    event_bus: EventBus | None = None,
    registry: AgentRegistry | None = None,
) -> AgentRuntime:
    """Build the production runtime and register its discoverable capability.

    ``event_bus`` is injectable so the bootstrap can be validated without
    requiring a live RabbitMQ connection. Production keeps RabbitMQ as the
    default adapter.
    """

    database_url = (os.getenv("RKJO_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
    bus = event_bus or RabbitMQEventBus()

    registry_backend = registry

    # Keep injected/test runtimes isolated in memory.
    # Production runtimes share discovery through PostgreSQL.
    if registry_backend is None:
        if event_bus is not None:
            registry_backend = AgentRegistry()
        else:
            database_url = (
                os.getenv("RKJO_DATABASE_URL")
                or os.getenv("DATABASE_URL")
                or ""
            ).strip()

            if not database_url:
                raise RuntimeError(
                    "DATABASE_URL or RKJO_DATABASE_URL "
                    "is required."
                )

            postgres_registry = (
                PostgresAgentRegistry(
                    database_url
                )
            )
            postgres_registry.initialize_schema()
            registry_backend = postgres_registry

    registry_service = RegistryService(
        registry=registry_backend
    )

    instance_id = uuid4().hex

    descriptor = build_platform_worker_descriptor()

    descriptor = descriptor.model_copy(
        update={
            "metadata": {
                **descriptor.metadata,
                "instance_id": instance_id,
            }
        }
    )

    agent = PlatformWorkerAgent(
        agent_name=descriptor.name,
        queue_name=descriptor.queue_name,
        event_bus=bus,
    )

    authorization = None
    authenticator = None
    if event_bus is None:
        authenticator = ResultAuthenticator.from_env()
        authorization = WorkflowAuthorization(
            uow_factory=lambda: PostgreSQLWorkflowUnitOfWork(database_url),
            reply_queue=get_env("RKJO_WORKFLOW_RESULT_QUEUE", "rkjo.workflow.results"),
        )

    result_publisher = AgentResultPublisher(
        event_bus=bus,
        source=descriptor.name,
        authenticator=authenticator,
    )

    return AgentRuntime(
        agent=agent,
        event_bus=bus,
        registry_service=registry_service,
        result_publisher=result_publisher,
        instance_id=instance_id,
        descriptor=descriptor,
        authorization=authorization,
    )


def main() -> None:
    runtime = build_runtime()

    health = RuntimeHealthAdapter(
        runtime=runtime,
        service_name="platform-worker",
    )

    health_server = HealthHTTPServer(
        health=health,
        host=get_env(
            "RKJO_WORKER_HEALTH_HOST",
            "0.0.0.0",
        ),
        port=int(
            get_env(
                "RKJO_WORKER_HEALTH_PORT",
                "8081",
            )
        ),
    )

    def _stop_handler(signum, frame) -> None:
        raise KeyboardInterrupt

    signal.signal(
        signal.SIGTERM,
        _stop_handler,
    )
    signal.signal(
        signal.SIGINT,
        _stop_handler,
    )

    heartbeat_stop = Event()
    def heartbeat():
        registry = runtime.registry_service.registry
        if not isinstance(registry, PostgresAgentRegistry):
            return
        interval = max(0.1, registry.lease_seconds / 3)
        while not heartbeat_stop.wait(interval):
            try:
                registry.heartbeat(runtime.agent.agent_name, runtime.instance_id)
            except Exception:
                # A failed heartbeat expires discovery; never advertise falsely.
                runtime.logger.exception("Worker registry heartbeat failed.")
    heartbeat_thread = Thread(target=heartbeat, daemon=True)

    try:
        heartbeat_thread.start()
        health_server.start()
        runtime.start()
    except KeyboardInterrupt:
        pass
    finally:
        heartbeat_stop.set()
        heartbeat_thread.join(timeout=2)
        health_server.stop()
        runtime.event_bus.close()


if __name__ == "__main__":
    main()
