from __future__ import annotations

import os
from uuid import uuid4

import pytest

from rkjo_kernel.harness.checkpoint import CheckpointService
from rkjo_kernel.harness.postgres import PostgresHarnessStateStore
from rkjo_kernel.harness.state import HarnessState, HarnessStateStatus

psycopg = pytest.importorskip("psycopg")
DATABASE_URL = os.getenv("RKJO_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="RKJO_TEST_DATABASE_URL is required for real PostgreSQL E2E",
)


def connection_factory():
    assert DATABASE_URL is not None
    return psycopg.connect(DATABASE_URL)


def test_checkpoint_survives_store_recreation_and_resumes():
    tenant_id = f"harness-tenant-{uuid4()}"
    mission_id = f"harness-mission-{uuid4()}"
    writer = PostgresHarnessStateStore(connection_factory, ensure_schema=True)
    service = CheckpointService(writer)
    saved = service.checkpoint(HarnessState(
        tenant_id=tenant_id,
        mission_id=mission_id,
        trace_id="trace-before-crash",
        status=HarnessStateStatus.RUNNING,
        iteration=3,
        data={"completed_steps": ["discover", "plan"]},
    ))
    try:
        restarted = CheckpointService(
            PostgresHarnessStateStore(connection_factory)
        )
        restored = restarted.resume(
            tenant_id=tenant_id,
            mission_id=mission_id,
        )
        assert restored.state_id == saved.state_id
        assert restored.checkpoint_version == 1
        assert restored.iteration == 3
        assert restored.data["completed_steps"] == ["discover", "plan"]
    finally:
        PostgresHarnessStateStore(connection_factory).delete(
            saved.state_id, tenant_id=tenant_id
        )


def test_postgres_checkpoint_does_not_leak_across_tenants():
    tenant_a = f"harness-a-{uuid4()}"
    tenant_b = f"harness-b-{uuid4()}"
    mission_id = f"harness-mission-{uuid4()}"
    store = PostgresHarnessStateStore(connection_factory, ensure_schema=True)
    saved = CheckpointService(store).checkpoint(HarnessState(
        tenant_id=tenant_a,
        mission_id=mission_id,
        trace_id="trace-a",
    ))
    try:
        assert store.get(saved.state_id, tenant_id=tenant_b) is None
        with pytest.raises(LookupError):
            CheckpointService(store).resume(
                tenant_id=tenant_b,
                mission_id=mission_id,
                state_id=saved.state_id,
            )
    finally:
        store.delete(saved.state_id, tenant_id=tenant_a)
