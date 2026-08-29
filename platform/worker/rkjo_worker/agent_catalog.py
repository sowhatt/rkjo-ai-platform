"""Shared catalog of RKJO production worker descriptors."""

from __future__ import annotations

import os

from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.services.registry_service import RegistryService


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


def build_platform_worker_descriptor(
    *,
    status: AgentStatus = AgentStatus.STOPPED,
) -> AgentDescriptor:
    """Build the canonical descriptor for the platform worker."""

    agent_name = get_env(
        "RKJO_WORKER_AGENT_NAME",
        "rkjo.platform.worker",
    )

    queue_name = get_env(
        "RKJO_WORKER_QUEUE",
        "rkjo.platform.worker",
    )

    capability_name = get_env(
        "RKJO_WORKER_CAPABILITY",
        "platform_task",
    )

    return AgentDescriptor(
        name=agent_name,
        display_name="RKJO Platform Worker",
        description=(
            "Generic distributed worker used to execute RKJO "
            "platform missions."
        ),
        product="RKJO",
        queue_name=queue_name,
        status=status,
        capabilities=[
            AgentCapability(
                name=capability_name,
                description=(
                    "Execute a generic RKJO platform mission and "
                    "return its processed payload."
                ),
                input_schema={
                    "payload": "dict",
                },
                output_schema={
                    "processed_by": "str",
                    "message_id": "str",
                    "payload": "dict",
                },
                tags=[
                    "rkjo",
                    "worker",
                    "runtime",
                ],
                supports_local_model=True,
            )
        ],
    )


def register_platform_worker(
    registry_service: RegistryService,
    *,
    status: AgentStatus = AgentStatus.STOPPED,
) -> AgentDescriptor:
    """Register the canonical platform worker descriptor."""

    descriptor = build_platform_worker_descriptor(
        status=status,
    )

    return registry_service.register_agent(
        descriptor
    )
