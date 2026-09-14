import os

import psycopg
import pytest

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.mission import ExecutionContext
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.idempotency import InMemoryProcessedMessageStore
from rkjo_kernel.workflow.models.workflow_definition import WorkflowDefinition
from rkjo_kernel.workflow.models.workflow_status import WorkflowStatus
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep
from rkjo_kernel.workflow.repository.postgres import PostgreSQLWorkflowRepository
from rkjo_kernel.workflow.result_handler import WorkflowResultHandler


DATABASE_URL = os.getenv(
    "RKJO_TEST_DATABASE_URL",
    "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
)


@pytest.fixture
def repository():
    repo = PostgreSQLWorkflowRepository(DATABASE_URL)
    repo.initialize_schema()

    yield repo

    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM workflow_executions;")


def make_definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="workflow-duplicate-e2e",
        name="Duplicate result E2E",
        steps=[
            WorkflowStep(
                step_id="teach",
                name="Teach",
                agent_name="education.tutor",
            )
        ],
    )


def test_duplicate_result_is_applied_once_and_trace_is_preserved(repository):
    engine = WorkflowEngine(repository=repository)

    execution = engine.create_execution(
        make_definition(),
        execution_id="duplicate-e2e-001",
        input_data={"topic": "fractions"},
    )

    execution.bind_execution_context(
        ExecutionContext(
            mission_id="mission-e2e-duplicate",
            trace_id="trace-e2e-duplicate",
        )
    )

    engine.start(execution)
    step = engine.start_next_step(execution)

    assert step is not None
    assert step.step_id == "teach"

    message = AgentMessage(
        message_id="result-duplicate-001",
        correlation_id="corr-duplicate-e2e-001",
        source="education.tutor",
        target="rkjo.workflow",
        message_type="workflow.step.result",
        payload={
            "success": True,
            "result": {
                "lesson": "fractions",
                "status": "completed",
            },
        },
        metadata={
            "mission_id": "mission-e2e-duplicate",
            "trace_id": "trace-e2e-duplicate",
            "workflow_execution_id": execution.execution_id,
            "workflow_step_id": "teach",
        },
    )

    processed = InMemoryProcessedMessageStore()
    handler = WorkflowResultHandler(
        engine=engine,
        processed_messages=processed,
    )

    handler.handle(message)

    first = repository.get(execution.execution_id)
    assert first is not None
    assert first.status == WorkflowStatus.COMPLETED
    assert first.context.outputs == {
        "teach": {
            "lesson": "fractions",
            "status": "completed",
        }
    }
    assert processed.contains(message.message_id)

    handler.handle(message)

    second = repository.get(execution.execution_id)
    assert second is not None
    assert second.status == WorkflowStatus.COMPLETED
    assert second.context.outputs == first.context.outputs
    assert processed.contains(message.message_id)

    assert message.metadata["mission_id"] == "mission-e2e-duplicate"
    assert message.metadata["trace_id"] == "trace-e2e-duplicate"
