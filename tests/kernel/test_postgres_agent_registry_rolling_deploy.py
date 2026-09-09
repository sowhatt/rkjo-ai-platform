import os
from uuid import uuid4

import psycopg

from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.postgres_registry import (
    PostgresAgentRegistry,
)


DATABASE_URL = os.getenv(
    "RKJO_TEST_DATABASE_URL",
    "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
)

AGENT_NAME = "rkjo.test.rolling-worker"


def make_descriptor(
    *,
    status: AgentStatus,
    instance_id: str,
) -> AgentDescriptor:
    return AgentDescriptor(
        name=AGENT_NAME,
        display_name="Rolling Worker",
        product="RKJO",
        queue_name="rkjo.test.rolling-worker",
        status=status,
        metadata={
            "instance_id": instance_id,
        },
    )


def clean_agent() -> None:
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM agent_registry "
                "WHERE name = %s;",
                (AGENT_NAME,),
            )


def test_stale_worker_cannot_stop_newer_instance():
    """
    Railway rolling deployment scenario:

    A registers.
    B replaces A.
    A shuts down afterwards.

    The stale A shutdown must not change B to STOPPED.
    """
    registry = PostgresAgentRegistry(DATABASE_URL)
    registry.initialize_schema()
    clean_agent()

    instance_a = str(uuid4())
    instance_b = str(uuid4())

    try:
        registry.register(
            make_descriptor(
                status=AgentStatus.AVAILABLE,
                instance_id=instance_a,
            )
        )

        registry.register(
            make_descriptor(
                status=AgentStatus.AVAILABLE,
                instance_id=instance_b,
            )
        )

        current = registry.find_by_name(AGENT_NAME)

        assert current is not None
        assert current.metadata["instance_id"] == instance_b
        assert current.status == AgentStatus.AVAILABLE

        registry.update_status(
            AGENT_NAME,
            AgentStatus.STOPPED,
            instance_id=instance_a,
        )

        current = registry.find_by_name(AGENT_NAME)

        assert current is not None
        assert current.metadata["instance_id"] == instance_b
        assert current.status == AgentStatus.AVAILABLE

    finally:
        clean_agent()
