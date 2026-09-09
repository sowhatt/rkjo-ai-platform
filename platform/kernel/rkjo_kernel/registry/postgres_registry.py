"""PostgreSQL-backed agent registry for distributed RKJO runtimes."""

from __future__ import annotations

import json

import psycopg

from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.registry import AgentRegistry


class PostgresAgentRegistry(AgentRegistry):
    """Share agent discovery state across API and worker processes."""

    def __init__(
        self,
        database_url: str,
    ) -> None:
        if not database_url or not database_url.strip():
            raise ValueError(
                "database_url must not be empty."
            )

        self.database_url = database_url

    def initialize_schema(self) -> None:
        query = """
        CREATE TABLE IF NOT EXISTS agent_registry (
            name TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            priority INTEGER NOT NULL,
            payload JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
                DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS
            idx_agent_registry_status
        ON agent_registry(status);

        CREATE INDEX IF NOT EXISTS
            idx_agent_registry_priority
        ON agent_registry(priority DESC);
        """

        with psycopg.connect(
            self.database_url
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)

    def register(
        self,
        descriptor: AgentDescriptor,
    ) -> None:
        query = """
        INSERT INTO agent_registry (
            name,
            status,
            priority,
            payload,
            updated_at
        )
        VALUES (
            %s,
            %s,
            %s,
            %s::jsonb,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (name)
        DO UPDATE SET
            status = EXCLUDED.status,
            priority = EXCLUDED.priority,
            payload = EXCLUDED.payload,
            updated_at = CURRENT_TIMESTAMP;
        """

        payload = descriptor.model_dump(
            mode="json"
        )

        with psycopg.connect(
            self.database_url
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        descriptor.name,
                        descriptor.status.value,
                        descriptor.priority,
                        json.dumps(payload),
                    ),
                )

    def unregister(
        self,
        agent_name: str,
    ) -> None:
        normalized_name = (
            agent_name.strip().lower()
        )

        query = """
        DELETE FROM agent_registry
        WHERE name = %s
        RETURNING name;
        """

        with psycopg.connect(
            self.database_url
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (normalized_name,),
                )
                row = cursor.fetchone()

        if row is None:
            raise KeyError(
                f"Agent '{normalized_name}' "
                "is not registered."
            )

    def find_by_name(
        self,
        agent_name: str,
    ) -> AgentDescriptor | None:
        normalized_name = (
            agent_name.strip().lower()
        )

        query = """
        SELECT payload
        FROM agent_registry
        WHERE name = %s;
        """

        with psycopg.connect(
            self.database_url
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (normalized_name,),
                )
                row = cursor.fetchone()

        if row is None:
            return None

        return AgentDescriptor.model_validate(
            row[0]
        )

    def list_agents(
        self,
    ) -> list[AgentDescriptor]:
        query = """
        SELECT payload
        FROM agent_registry
        ORDER BY name ASC;
        """

        with psycopg.connect(
            self.database_url
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

        return [
            AgentDescriptor.model_validate(row[0])
            for row in rows
        ]

    def find_available_agents(
        self,
    ) -> list[AgentDescriptor]:
        return [
            descriptor
            for descriptor in self.list_agents()
            if descriptor.is_available()
        ]

    def find_by_capability(
        self,
        capability_name: str,
        only_available: bool = True,
    ) -> list[AgentDescriptor]:
        normalized_capability = (
            capability_name.strip().lower()
        )

        matching_agents = [
            descriptor
            for descriptor in self.list_agents()
            if descriptor.has_capability(
                normalized_capability
            )
        ]

        if only_available:
            matching_agents = [
                descriptor
                for descriptor in matching_agents
                if descriptor.is_available()
            ]

        return sorted(
            matching_agents,
            key=lambda descriptor: (
                descriptor.priority
            ),
            reverse=True,
        )

    def update_status(
        self,
        agent_name: str,
        status: AgentStatus,
    ) -> AgentDescriptor:
        descriptor = self.find_by_name(
            agent_name
        )

        if descriptor is None:
            raise KeyError(
                f"Agent '{agent_name}' "
                "is not registered."
            )

        updated_descriptor = (
            descriptor.model_copy(
                update={
                    "status": status,
                }
            )
        )

        self.register(
            updated_descriptor
        )

        return updated_descriptor

    def count(self) -> int:
        query = """
        SELECT COUNT(*)
        FROM agent_registry;
        """

        with psycopg.connect(
            self.database_url
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                row = cursor.fetchone()

        return int(row[0]) if row else 0
