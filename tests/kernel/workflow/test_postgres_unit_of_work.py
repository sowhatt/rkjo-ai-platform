import os
from datetime import datetime, timezone

import psycopg
import pytest

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.models.workflow_definition import (
    WorkflowDefinition,
)
from rkjo_kernel.workflow.models.workflow_step import (
    WorkflowStep,
)
from rkjo_kernel.workflow.outbox import OutboxMessage
from rkjo_kernel.workflow.postgres_unit_of_work import (
    PostgreSQLWorkflowUnitOfWork,
)


DATABASE_URL = os.getenv(
    "RKJO_TEST_DATABASE_URL",
    "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
)


def make_definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="workflow-uow-postgres",
        name="PostgreSQL UoW Workflow",
        steps=[
            WorkflowStep(
                step_id="weather",
                name="Weather",
                capability_name="weather.analysis",
                position=0,
            )
        ],
    )


def make_execution(
    execution_id: str,
):
    engine = WorkflowEngine()
    return engine.create_execution(
        make_definition(),
        execution_id=execution_id,
    )


def make_outbox_message(
    outbox_id: str,
) -> OutboxMessage:
    return OutboxMessage(
        outbox_id=outbox_id,
        queue_name="weather.agent",
        message=AgentMessage(
            message_id=f"message-{outbox_id}",
            correlation_id=f"corr-{outbox_id}",
            source="rkjo.workflow",
            target="weather.agent",
            message_type="workflow.step.execute",
            payload={
                "input_data": {},
            },
            metadata={
                "workflow_execution_id": (
                    f"execution-{outbox_id}"
                ),
                "workflow_step_id": "weather",
            },
        ),
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def uow():
    instance = PostgreSQLWorkflowUnitOfWork(
        DATABASE_URL
    )
    instance.initialize_schema()

    with psycopg.connect(
        DATABASE_URL
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM workflow_outbox;"
            )
            cursor.execute(
                "DELETE FROM workflow_inbox;"
            )
            cursor.execute(
                "DELETE FROM workflow_executions;"
            )

    yield instance

    with psycopg.connect(
        DATABASE_URL
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM workflow_outbox;"
            )
            cursor.execute(
                "DELETE FROM workflow_inbox;"
            )
            cursor.execute(
                "DELETE FROM workflow_executions;"
            )


def test_commit_persists_workflow_inbox_and_outbox(
    uow,
):
    execution = make_execution(
        "postgres-uow-commit-001"
    )
    outbox = make_outbox_message(
        "outbox-commit-001"
    )

    with uow:
        uow.workflows.save(execution)
        uow.inbox.mark_processed(
            "result-commit-001"
        )
        uow.outbox.add(outbox)
        uow.commit()

    with PostgreSQLWorkflowUnitOfWork(
        DATABASE_URL
    ) as verification:
        assert verification.workflows.get(
            execution.execution_id
        ) is not None

        assert verification.inbox.contains(
            "result-commit-001"
        )

        pending = verification.outbox.pending()

        assert len(pending) == 1
        assert pending[0].outbox_id == (
            "outbox-commit-001"
        )


def test_no_commit_rolls_back_all_changes(
    uow,
):
    execution = make_execution(
        "postgres-uow-rollback-001"
    )
    outbox = make_outbox_message(
        "outbox-rollback-001"
    )

    with uow:
        uow.workflows.save(execution)
        uow.inbox.mark_processed(
            "result-rollback-001"
        )
        uow.outbox.add(outbox)

    with PostgreSQLWorkflowUnitOfWork(
        DATABASE_URL
    ) as verification:
        assert verification.workflows.get(
            execution.execution_id
        ) is None

        assert not verification.inbox.contains(
            "result-rollback-001"
        )

        assert verification.outbox.pending() == []


def test_exception_rolls_back_all_changes(
    uow,
):
    execution = make_execution(
        "postgres-uow-exception-001"
    )
    outbox = make_outbox_message(
        "outbox-exception-001"
    )

    with pytest.raises(
        RuntimeError,
        match="simulated transaction failure",
    ):
        with uow:
            uow.workflows.save(execution)
            uow.inbox.mark_processed(
                "result-exception-001"
            )
            uow.outbox.add(outbox)

            raise RuntimeError(
                "simulated transaction failure"
            )

    with PostgreSQLWorkflowUnitOfWork(
        DATABASE_URL
    ) as verification:
        assert verification.workflows.get(
            execution.execution_id
        ) is None

        assert not verification.inbox.contains(
            "result-exception-001"
        )

        assert verification.outbox.pending() == []


def test_commit_survives_new_connection(
    uow,
):
    execution = make_execution(
        "postgres-uow-restart-001"
    )
    outbox = make_outbox_message(
        "outbox-restart-001"
    )

    with uow:
        uow.workflows.save(execution)
        uow.inbox.mark_processed(
            "result-restart-001"
        )
        uow.outbox.add(outbox)
        uow.commit()

    restarted = PostgreSQLWorkflowUnitOfWork(
        DATABASE_URL
    )

    with restarted:
        restored = restarted.workflows.get(
            execution.execution_id
        )

        assert restored is not None
        assert restored.execution_id == (
            "postgres-uow-restart-001"
        )

        assert restarted.inbox.contains(
            "result-restart-001"
        )

        pending = restarted.outbox.pending()

        assert len(pending) == 1
        assert pending[0].outbox_id == (
            "outbox-restart-001"
        )


def test_mark_published_is_transactional(
    uow,
):
    message = make_outbox_message(
        "outbox-publish-001"
    )

    with uow:
        uow.outbox.add(message)
        uow.commit()

    with uow:
        uow.outbox.mark_published(
            message.outbox_id
        )

    with PostgreSQLWorkflowUnitOfWork(
        DATABASE_URL
    ) as verification:
        pending = verification.outbox.pending()

        assert len(pending) == 1
        assert pending[0].outbox_id == (
            "outbox-publish-001"
        )

    with uow:
        uow.outbox.mark_published(
            message.outbox_id
        )
        uow.commit()

    with PostgreSQLWorkflowUnitOfWork(
        DATABASE_URL
    ) as verification:
        assert verification.outbox.pending() == []


def test_pending_skips_rows_locked_by_another_transaction(
    uow,
):
    """Concurrent outbox publishers must not claim the same row."""

    first_message = make_outbox_message(
        "outbox-concurrent-001"
    )

    second_message = make_outbox_message(
        "outbox-concurrent-002"
    )

    with uow:
        uow.outbox.add(
            first_message
        )
        uow.outbox.add(
            second_message
        )
        uow.commit()

    first_worker = PostgreSQLWorkflowUnitOfWork(
        DATABASE_URL
    )

    second_worker = PostgreSQLWorkflowUnitOfWork(
        DATABASE_URL
    )

    with first_worker:
        first_pending = (
            first_worker.outbox.pending(
                limit=1
            )
        )

        assert len(first_pending) == 1

        first_id = (
            first_pending[0].outbox_id
        )

        # first_worker keeps its PostgreSQL transaction
        # open here, so its selected row remains locked.
        with second_worker:
            second_pending = (
                second_worker.outbox.pending(
                    limit=1
                )
            )

            assert len(second_pending) == 1

            second_id = (
                second_pending[0].outbox_id
            )

            assert second_id != first_id

            assert {
                first_id,
                second_id,
            } == {
                "outbox-concurrent-001",
                "outbox-concurrent-002",
            }
