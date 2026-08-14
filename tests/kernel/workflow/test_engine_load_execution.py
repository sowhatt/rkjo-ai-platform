
import pytest

from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.models.workflow_definition import (
    WorkflowDefinition,
)
from rkjo_kernel.workflow.models.workflow_status import WorkflowStatus
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep
from rkjo_kernel.workflow.repository.memory import (
    InMemoryWorkflowRepository,
)


def make_definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="workflow-load",
        name="Load Workflow",
        steps=[
            WorkflowStep(
                step_id="step-001",
                name="Step 1",
                agent_name="test-agent",
            )
        ],
    )


def test_load_execution_returns_persisted_execution():
    repository = InMemoryWorkflowRepository()
    engine = WorkflowEngine(
        repository=repository
    )

    execution = engine.create_execution(
        make_definition(),
        execution_id="load-001",
    )

    engine.start(execution)

    restored = engine.load_execution(
        "load-001"
    )

    assert restored.execution_id == "load-001"
    assert restored.status == WorkflowStatus.RUNNING


def test_load_execution_raises_when_not_found():
    repository = InMemoryWorkflowRepository()
    engine = WorkflowEngine(
        repository=repository
    )

    with pytest.raises(
        KeyError,
        match="Unknown workflow execution",
    ):
        engine.load_execution(
            "unknown"
        )


def test_load_execution_requires_repository():
    engine = WorkflowEngine()

    with pytest.raises(
        RuntimeError,
        match="requires a repository",
    ):
        engine.load_execution(
            "load-001"
        )
