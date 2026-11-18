from __future__ import annotations

import os
from uuid import uuid4

import pytest

from rkjo_kernel.memory import ContextEngine, MissionMemoryService, PostgresMemoryStore
from rkjo_kernel.mission.execution_context import ExecutionContext

psycopg = pytest.importorskip("psycopg")

DATABASE_URL = os.getenv("RKJO_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="RKJO_TEST_DATABASE_URL is required for real PostgreSQL E2E",
)


def connection_factory():
    assert DATABASE_URL is not None
    return psycopg.connect(DATABASE_URL)


def context(*, tenant_id: str, mission_id: str, trace_id: str) -> ExecutionContext:
    return ExecutionContext(
        tenant_id=tenant_id,
        mission_id=mission_id,
        trace_id=trace_id,
        user_id="postgres-e2e-user",
    )


def cleanup(memory_id: str, tenant_id: str) -> None:
    PostgresMemoryStore(connection_factory).delete(memory_id, tenant_id=tenant_id)


def test_memory_survives_store_recreation_and_reaches_context_engine():
    tenant_id = f"e2e-tenant-{uuid4()}"
    mission_id = f"e2e-mission-{uuid4()}"
    first_context = context(
        tenant_id=tenant_id,
        mission_id=mission_id,
        trace_id="trace-write",
    )

    writer = PostgresMemoryStore(connection_factory, ensure_schema=True)
    stored = MissionMemoryService(writer).remember(
        context=first_context,
        content="S11 durable mission memory survives process recreation.",
        importance=0.99,
        metadata={"test": "postgres-e2e"},
    )

    try:
        # A new store instance models a restarted worker/process.
        restarted_store = PostgresMemoryStore(connection_factory)
        read_context = context(
            tenant_id=tenant_id,
            mission_id=mission_id,
            trace_id="trace-read",
        )
        package = ContextEngine(restarted_store).build(context=read_context)

        assert [item.memory_id for item in package.items] == [stored.memory_id]
        assert package.items[0].content == stored.content
        assert package.items[0].metadata["test"] == "postgres-e2e"
        assert package.tenant_id == tenant_id
        assert package.mission_id == mission_id
        assert package.trace_id == "trace-read"
    finally:
        cleanup(stored.memory_id, tenant_id)


def test_real_postgres_does_not_leak_memory_across_tenants():
    tenant_a = f"e2e-tenant-a-{uuid4()}"
    tenant_b = f"e2e-tenant-b-{uuid4()}"
    mission_id = f"e2e-shared-mission-{uuid4()}"
    store = PostgresMemoryStore(connection_factory, ensure_schema=True)

    stored = MissionMemoryService(store).remember(
        context=context(
            tenant_id=tenant_a,
            mission_id=mission_id,
            trace_id="trace-a",
        ),
        content="Tenant A private durable memory.",
    )

    try:
        package = ContextEngine(PostgresMemoryStore(connection_factory)).build(
            context=context(
                tenant_id=tenant_b,
                mission_id=mission_id,
                trace_id="trace-b",
            )
        )
        assert package.items == ()
        assert (
            PostgresMemoryStore(connection_factory).get(
                stored.memory_id,
                tenant_id=tenant_b,
            )
            is None
        )
    finally:
        cleanup(stored.memory_id, tenant_a)


def test_real_postgres_rejects_cross_tenant_memory_id_collision():
    tenant_a = f"e2e-tenant-a-{uuid4()}"
    tenant_b = f"e2e-tenant-b-{uuid4()}"
    mission_id = f"e2e-mission-{uuid4()}"
    store = PostgresMemoryStore(connection_factory, ensure_schema=True)

    stored = MissionMemoryService(store).remember(
        context=context(
            tenant_id=tenant_a,
            mission_id=mission_id,
            trace_id="trace-a",
        ),
        content="Original tenant-owned memory.",
    )

    try:
        from dataclasses import replace

        with pytest.raises(ValueError, match="tenant boundary"):
            store.write(
                replace(
                    stored,
                    tenant_id=tenant_b,
                    mission_id=mission_id,
                    content="Attempted cross-tenant overwrite.",
                )
            )

        restored = store.get(stored.memory_id, tenant_id=tenant_a)
        assert restored is not None
        assert restored.content == "Original tenant-owned memory."
    finally:
        cleanup(stored.memory_id, tenant_a)
