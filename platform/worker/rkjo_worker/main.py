"""Production worker bootstrap for RKJO AI Platform."""

from __future__ import annotations

import os
import signal
from typing import Any

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
from rkjo_kernel.runtime.agent_runtime import AgentRuntime
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
) -> AgentRuntime:
    """Build the production runtime and register its discoverable capability.

    ``event_bus`` is injectable so the bootstrap can be validated without
    requiring a live RabbitMQ connection. Production keeps RabbitMQ as the
    default adapter.
    """

    bus = event_bus or RabbitMQEventBus()

    registry = AgentRegistry()

    registry_service = RegistryService(
        registry=registry
    )

    descriptor = build_platform_worker_descriptor()

    registry_service.register_agent(
        descriptor
    )

    agent = PlatformWorkerAgent(
        agent_name=descriptor.name,
        queue_name=descriptor.queue_name,
        event_bus=bus,
    )

    return AgentRuntime(
        agent=agent,
        event_bus=bus,
        registry_service=registry_service,
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

    try:
        health_server.start()
        runtime.start()
    except KeyboardInterrupt:
        pass
    finally:
        health_server.stop()
        runtime.event_bus.close()


if __name__ == "__main__":
    main()
