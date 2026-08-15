"""Production worker bootstrap for RKJO AI Platform."""

from __future__ import annotations

import os
from typing import Any

from rkjo_kernel.agents.base_agent import BaseAgent
from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
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


def build_runtime() -> AgentRuntime:
    agent_name = get_env(
        "RKJO_WORKER_AGENT_NAME",
        "rkjo.platform.worker",
    )

    queue_name = get_env(
        "RKJO_WORKER_QUEUE",
        "rkjo.platform.worker",
    )

    bus = RabbitMQEventBus()

    registry = AgentRegistry()

    registry_service = RegistryService(
        registry=registry
    )

    registry_service.register_agent(
        AgentDescriptor(
            name=agent_name,
            display_name="RKJO Platform Worker",
            product="RKJO",
            queue_name=queue_name,
            status=AgentStatus.STOPPED,
        )
    )

    agent = PlatformWorkerAgent(
        agent_name=agent_name,
        queue_name=queue_name,
        event_bus=bus,
    )

    return AgentRuntime(
        agent=agent,
        event_bus=bus,
        registry_service=registry_service,
    )


def main() -> None:
    runtime = build_runtime()

    runtime.start()


if __name__ == "__main__":
    main()
