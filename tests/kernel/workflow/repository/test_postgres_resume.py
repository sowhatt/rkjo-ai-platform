
import os

import psycopg
import pytest

from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.models.workflow_definition import (
    WorkflowDefinition,
)
from rkjo_kernel.workflow.models.workflow_status import (
    WorkflowStatus,
)
from rkjo_kernel.workflow.models.workflow_step import (
    WorkflowStep,
)
from rkjo_kernel.workflow.repository.postgres import (
    PostgreSQLWorkflowRepository,
)


DATABASE_URL = os.getenv(
    "RKJO_TEST_DATABASE_URL",
    "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
)


def make_definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="workflow-resume",
        name="Resume Workflow",
        steps=[
            WorkflowStep(
                step_id="weather",
                name="Weather Analysis",
                capability_name="weather.analysis",
                position=0,
            ),
            WorkflowStep(
                step_id="risk",
                name="Risk Analysis",
                capability_name="risk.analysis",
                position=1,
            ),
        ],
    )


@pytest.fixture
def repository():
    repo = PostgreSQLWorkflowRepository(
        DATABASE_URL
    )

    repo.initialize_schema()

    yield repo

    with psycopg.connect(
        DATABASE_URL
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM workflow_executions;"
            )


def test_running_workflow_can_resume_after_repository_restart(
    repository,
):
    engine_a = WorkflowEngine(
        repository=repository
    )

    execution = engine_a.create_execution(
        make_definition(),
        execution_id="resume-001",
    )

    engine_a.start(execution)
    engine_a.start_next_step(execution)

    engine_a.complete_current_step(
        execution,
        output={
            "temperature": 31,
        },
    )

    assert execution.status == WorkflowStatus.RUNNING
    assert execution.current_step_id is None

    # Simulate process restart:
    # brand-new repository and engine instances.
    repository_b = PostgreSQLWorkflowRepository(
        DATABASE_URL
    )

    restored = repository_b.get(
        "resume-001"
    )

    assert restored is not None
    assert restored.status == WorkflowStatus.RUNNING

    assert restored.context.outputs == {
        "weather": {
            "temperature": 31,
        }
    }

    engine_b = WorkflowEngine(
        repository=repository_b
    )

    next_step = engine_b.start_next_step(
        restored
    )

    assert next_step is not None
    assert next_step.step_id == "risk"
    assert restored.current_step_id == "risk"

    engine_b.complete_current_step(
        restored,
        output={
            "risk_score": 0.72,
        },
    )

    engine_b.complete(restored)

    final_state = repository_b.get(
        "resume-001"
    )

    assert final_state is not None
    assert final_state.status == WorkflowStatus.COMPLETED
    assert final_state.current_step_id is None

    assert final_state.context.outputs == {
        "weather": {
            "temperature": 31,
        },
        "risk": {
            "risk_score": 0.72,
        },
    }


def test_pending_workflow_can_be_loaded_and_started_after_restart(
    repository,
):
    engine_a = WorkflowEngine(
        repository=repository
    )

    engine_a.create_execution(
        make_definition(),
        execution_id="resume-pending-001",
    )

    repository_b = PostgreSQLWorkflowRepository(
        DATABASE_URL
    )

    restored = repository_b.get(
        "resume-pending-001"
    )

    assert restored is not None
    assert restored.status == WorkflowStatus.PENDING

    engine_b = WorkflowEngine(
        repository=repository_b
    )

    engine_b.start(restored)

    stored = repository_b.get(
        "resume-pending-001"
    )

    assert stored is not None
    assert stored.status == WorkflowStatus.RUNNING
    assert stored.started_at is not None
