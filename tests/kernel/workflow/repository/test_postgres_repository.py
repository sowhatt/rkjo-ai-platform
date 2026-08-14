
import os

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
        workflow_id="workflow-integration",
        name="PostgreSQL Integration Workflow",
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

    with __import__("psycopg").connect(
        DATABASE_URL
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM workflow_executions;"
            )


def test_postgres_save_and_get(repository):
    engine = WorkflowEngine()

    execution = engine.create_execution(
        make_definition(),
        execution_id="postgres-001",
        input_data={
            "parcel_id": "P-100",
        },
        metadata={
            "product": "ADIP",
        },
    )

    engine.start(execution)

    repository.save(execution)

    stored = repository.get(
        execution.execution_id
    )

    assert stored is not None
    assert stored.execution_id == "postgres-001"
    assert stored.status == WorkflowStatus.RUNNING
    assert stored.context.input_data == {
        "parcel_id": "P-100"
    }
    assert stored.metadata == {
        "product": "ADIP"
    }


def test_postgres_new_repository_instance_can_restore_execution(
    repository,
):
    engine = WorkflowEngine()

    execution = engine.create_execution(
        make_definition(),
        execution_id="postgres-restart-001",
    )

    engine.start(execution)
    engine.start_next_step(execution)

    repository.save(execution)

    new_repository = PostgreSQLWorkflowRepository(
        DATABASE_URL
    )

    restored = new_repository.get(
        "postgres-restart-001"
    )

    assert restored is not None
    assert restored.execution_id == (
        "postgres-restart-001"
    )
    assert restored.status == WorkflowStatus.RUNNING
    assert restored.current_step_id == "weather"
    assert restored.current_step is not None
    assert restored.current_step.status.value == "running"


def test_postgres_save_updates_existing_execution(
    repository,
):
    engine = WorkflowEngine()

    execution = engine.create_execution(
        make_definition(),
        execution_id="postgres-update-001",
    )

    repository.save(execution)

    engine.start(execution)

    repository.save(execution)

    restored = repository.get(
        execution.execution_id
    )

    assert restored is not None
    assert restored.status == WorkflowStatus.RUNNING
    assert restored.started_at is not None

    assert len(repository.list_all()) == 1


def test_postgres_exists(repository):
    engine = WorkflowEngine()

    execution = engine.create_execution(
        make_definition(),
        execution_id="postgres-exists-001",
    )

    assert repository.exists(
        execution.execution_id
    ) is False

    repository.save(execution)

    assert repository.exists(
        execution.execution_id
    ) is True


def test_postgres_delete(repository):
    engine = WorkflowEngine()

    execution = engine.create_execution(
        make_definition(),
        execution_id="postgres-delete-001",
    )

    repository.save(execution)

    repository.delete(
        execution.execution_id
    )

    assert repository.get(
        execution.execution_id
    ) is None


def test_postgres_list_all(repository):
    engine = WorkflowEngine()

    first = engine.create_execution(
        make_definition(),
        execution_id="postgres-list-001",
    )

    second = engine.create_execution(
        make_definition(),
        execution_id="postgres-list-002",
    )

    repository.save(first)
    repository.save(second)

    stored = repository.list_all()

    assert {
        item.execution_id
        for item in stored
    } == {
        "postgres-list-001",
        "postgres-list-002",
    }


def test_workflow_engine_can_persist_directly_to_postgres(
    repository,
):
    engine = WorkflowEngine(
        repository=repository
    )

    execution = engine.create_execution(
        make_definition(),
        execution_id="postgres-engine-001",
    )

    engine.start(execution)
    engine.start_next_step(execution)

    engine.complete_current_step(
        execution,
        output={
            "rainfall": 14.2,
        },
    )

    restored = repository.get(
        execution.execution_id
    )

    assert restored is not None
    assert restored.status == WorkflowStatus.RUNNING
    assert restored.current_step_id is None

    assert restored.context.outputs == {
        "weather": {
            "rainfall": 14.2
        }
    }

    assert (
        restored.definition.steps[0]
        .status.value
        == "completed"
    )
