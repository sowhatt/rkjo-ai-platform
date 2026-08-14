import os

import psycopg
import pytest

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.models.workflow_definition import (
    WorkflowDefinition,
)
from rkjo_kernel.workflow.models.workflow_status import WorkflowStatus
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep
from rkjo_kernel.workflow.postgres_idempotency import (
    PostgreSQLProcessedMessageStore,
)
from rkjo_kernel.workflow.repository.postgres import (
    PostgreSQLWorkflowRepository,
)
from rkjo_kernel.workflow.result_handler import WorkflowResultHandler


DATABASE_URL = os.getenv(
    "RKJO_TEST_DATABASE_URL",
    "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
)


@pytest.fixture
def stores():
    workflow_repository = PostgreSQLWorkflowRepository(
        DATABASE_URL
    )

    idempotency_store = PostgreSQLProcessedMessageStore(
        DATABASE_URL
    )

    workflow_repository.initialize_schema()
    idempotency_store.initialize_schema()

    yield workflow_repository, idempotency_store

    with psycopg.connect(
        DATABASE_URL
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM workflow_executions;"
            )
            cursor.execute(
                "DELETE FROM processed_messages;"
            )


def make_definition():
    return WorkflowDefinition(
        workflow_id="workflow-idempotency-postgres",
        name="PostgreSQL Idempotency Workflow",
        steps=[
            WorkflowStep(
                step_id="weather",
                name="Weather",
                capability_name="weather.analysis",
            )
        ],
    )


def make_result_message():
    return AgentMessage(
        message_id="result-postgres-001",
        correlation_id="corr-postgres-001",
        source="weather.agent",
        target="rkjo.workflow",
        message_type="workflow.step.result",
        payload={
            "success": True,
            "result": {
                "temperature": 31,
            },
        },
        metadata={
            "workflow_execution_id": (
                "exec-idempotency-postgres-001"
            ),
            "workflow_step_id": "weather",
        },
    )


def test_processed_message_survives_store_restart(
    stores,
):
    _, store_a = stores

    store_a.mark_processed(
        "message-001"
    )

    store_b = PostgreSQLProcessedMessageStore(
        DATABASE_URL
    )

    assert store_b.contains(
        "message-001"
    )


def test_mark_processed_is_idempotent(
    stores,
):
    _, store = stores

    store.mark_processed(
        "message-001"
    )

    store.mark_processed(
        "message-001"
    )

    assert store.contains(
        "message-001"
    )


def test_duplicate_result_after_restart_is_ignored(
    stores,
):
    workflow_repository, store_a = stores

    engine_a = WorkflowEngine(
        repository=workflow_repository
    )

    execution = engine_a.create_execution(
        make_definition(),
        execution_id=(
            "exec-idempotency-postgres-001"
        ),
    )

    engine_a.start(execution)
    engine_a.start_next_step(execution)

    handler_a = WorkflowResultHandler(
        engine=engine_a,
        processed_messages=store_a,
    )

    message = make_result_message()

    handler_a.handle(message)

    first_state = workflow_repository.get(
        execution.execution_id
    )

    assert first_state is not None
    assert first_state.status == (
        WorkflowStatus.COMPLETED
    )

    # Simulate application restart.
    workflow_repository_b = (
        PostgreSQLWorkflowRepository(
            DATABASE_URL
        )
    )

    store_b = PostgreSQLProcessedMessageStore(
        DATABASE_URL
    )

    engine_b = WorkflowEngine(
        repository=workflow_repository_b
    )

    handler_b = WorkflowResultHandler(
        engine=engine_b,
        processed_messages=store_b,
    )

    # Same RabbitMQ result redelivered.
    handler_b.handle(message)

    second_state = workflow_repository_b.get(
        execution.execution_id
    )

    assert second_state is not None

    assert second_state.status == (
        WorkflowStatus.COMPLETED
    )

    assert second_state.context.outputs == {
        "weather": {
            "temperature": 31,
        }
    }

    assert store_b.contains(
        message.message_id
    )


def test_unknown_message_is_not_processed(
    stores,
):
    _, store = stores

    assert store.contains(
        "unknown-message"
    ) is False
