from __future__ import annotations

import os
from uuid import uuid4

import pytest

from rkjo_kernel.harness import CheckpointService
from rkjo_kernel.harness.postgres import PostgresHarnessStateStore
from rkjo_kernel.harness.runtime import AgentHarness, HarnessIterationResult
from rkjo_kernel.harness.state import HarnessStateStatus
from rkjo_kernel.mission.execution_context import ExecutionContext

psycopg = pytest.importorskip("psycopg")
DATABASE_URL = os.getenv("RKJO_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="RKJO_TEST_DATABASE_URL is required for crash/restart E2E",
)


def connection_factory():
    assert DATABASE_URL is not None
    return psycopg.connect(DATABASE_URL)


def test_mission_resumes_after_runtime_recreation_without_replaying_completed_work():
    tenant_id = f"harness-crash-{uuid4()}"
    mission_id = f"harness-mission-{uuid4()}"
    context = ExecutionContext(
        tenant_id=tenant_id,
        mission_id=mission_id,
        trace_id=f"trace-{uuid4()}",
    )
    side_effects: list[str] = []

    def executor(*, state, context):
        completed = list(state.data.get("completed_steps", []))
        if "discover" not in completed:
            side_effects.append("discover")
            completed.append("discover")
            return HarnessIterationResult(
                output="discovered",
                data={"completed_steps": completed},
            )
        if "plan" not in completed:
            side_effects.append("plan")
            completed.append("plan")
            return HarnessIterationResult(
                output="planned",
                data={"completed_steps": completed},
            )
        side_effects.append("execute")
        completed.append("execute")
        return HarnessIterationResult(
            output="done",
            data={"completed_steps": completed},
            completed=True,
        )

    first_store = PostgresHarnessStateStore(
        connection_factory,
        ensure_schema=True,
    )
    first_runtime = AgentHarness(
        checkpoints=CheckpointService(first_store),
        executor=executor,
    )
    state = first_runtime.start(context=context)
    state = first_runtime.run_iteration(context=context, state=state)
    state = first_runtime.run_iteration(context=context, state=state)

    assert side_effects == ["discover", "plan"]
    assert state.iteration == 2
    state_id = state.state_id

    try:
        # Simulated process crash: discard all runtime/store/service objects.
        del first_runtime
        del first_store

        restarted_runtime = AgentHarness(
            checkpoints=CheckpointService(
                PostgresHarnessStateStore(connection_factory)
            ),
            executor=executor,
        )
        restored = restarted_runtime.resume(
            context=context,
            state_id=state_id,
        )

        assert restored.iteration == 2
        assert restored.data["completed_steps"] == ["discover", "plan"]

        completed = restarted_runtime.run_iteration(
            context=context,
            state=restored,
        )

        assert completed.status is HarnessStateStatus.COMPLETED
        assert completed.iteration == 3
        assert completed.data["completed_steps"] == [
            "discover",
            "plan",
            "execute",
        ]
        assert side_effects == ["discover", "plan", "execute"]

        persisted = PostgresHarnessStateStore(connection_factory).get(
            state_id,
            tenant_id=tenant_id,
        )
        assert persisted is not None
        assert persisted.status is HarnessStateStatus.COMPLETED
        assert persisted.iteration == 3
    finally:
        PostgresHarnessStateStore(connection_factory).delete(
            state_id,
            tenant_id=tenant_id,
        )
