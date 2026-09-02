import os

import psycopg
import pytest

from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.models.workflow_definition import (
    WorkflowDefinition,
)
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep
from rkjo_kernel.workflow.postgres_unit_of_work import (
    PostgreSQLWorkflowUnitOfWork,
)


DATABASE_URL = os.getenv(
    "RKJO_TEST_DATABASE_URL",
    "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
)

EXECUTION_ID = "postgres-row-lock-001"


def make_execution():
    definition = WorkflowDefinition(
        workflow_id="workflow-row-lock",
        name="Workflow Row Lock",
        steps=[
            WorkflowStep(
                step_id="step-1",
                name="Step 1",
                capability_name="test.capability",
                position=0,
            )
        ],
    )

    return WorkflowEngine().create_execution(
        definition,
        execution_id=EXECUTION_ID,
    )


def clean_execution() -> None:
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM workflow_executions "
                "WHERE execution_id = %s;",
                (EXECUTION_ID,),
            )


def test_get_holds_row_lock_until_transaction_finishes():
    """Only one transaction may mutate the same workflow at a time."""
    bootstrap = PostgreSQLWorkflowUnitOfWork(DATABASE_URL)
    bootstrap.initialize_schema()
    clean_execution()

    try:
        with PostgreSQLWorkflowUnitOfWork(DATABASE_URL) as setup:
            setup.workflows.save(make_execution())
            setup.commit()

        first = PostgreSQLWorkflowUnitOfWork(DATABASE_URL)
        second = PostgreSQLWorkflowUnitOfWork(DATABASE_URL)

        with first:
            locked = first.workflows.get(EXECUTION_ID)
            assert locked is not None

            with second:
                assert second._connection is not None

                with second._connection.cursor() as cursor:
                    cursor.execute(
                        "SET LOCAL lock_timeout = '100ms';"
                    )

                with pytest.raises(psycopg.errors.LockNotAvailable):
                    second.workflows.get(EXECUTION_ID)

        # Once the first transaction is closed, the row can be acquired again.
        with PostgreSQLWorkflowUnitOfWork(DATABASE_URL) as verification:
            restored = verification.workflows.get(EXECUTION_ID)
            assert restored is not None
            assert restored.execution_id == EXECUTION_ID
    finally:
        clean_execution()
