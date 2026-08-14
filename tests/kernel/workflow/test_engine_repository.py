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
        workflow_id="workflow-persistence",
        name="Persistence Workflow",
        steps=[
            WorkflowStep(
                step_id="step-001",
                name="First Step",
                agent_name="test-agent",
            )
        ],
    )


def test_create_execution_is_persisted():
    repository = InMemoryWorkflowRepository()
    engine = WorkflowEngine(repository=repository)

    execution = engine.create_execution(
        make_definition(),
        execution_id="execution-001",
    )

    stored = repository.get("execution-001")

    assert stored is not None
    assert stored.execution_id == execution.execution_id
    assert stored.status == WorkflowStatus.PENDING


def test_start_execution_updates_repository():
    repository = InMemoryWorkflowRepository()
    engine = WorkflowEngine(repository=repository)

    execution = engine.create_execution(
        make_definition(),
        execution_id="execution-001",
    )

    engine.start(execution)

    stored = repository.get("execution-001")

    assert stored is not None
    assert stored.status == WorkflowStatus.RUNNING
    assert stored.started_at is not None


def test_start_next_step_updates_repository():
    repository = InMemoryWorkflowRepository()
    engine = WorkflowEngine(repository=repository)

    execution = engine.create_execution(
        make_definition(),
        execution_id="execution-001",
    )

    engine.start(execution)
    engine.start_next_step(execution)

    stored = repository.get("execution-001")

    assert stored is not None
    assert stored.current_step_id == "step-001"
    assert stored.current_step is not None
    assert stored.current_step.status.value == "running"


def test_complete_current_step_updates_repository():
    repository = InMemoryWorkflowRepository()
    engine = WorkflowEngine(repository=repository)

    execution = engine.create_execution(
        make_definition(),
        execution_id="execution-001",
    )

    engine.start(execution)
    engine.start_next_step(execution)

    engine.complete_current_step(
        execution,
        output={"score": 42},
    )

    stored = repository.get("execution-001")

    assert stored is not None
    assert stored.current_step_id is None
    assert stored.context.outputs["step-001"] == {
        "score": 42
    }
    assert stored.definition.steps[0].status.value == "completed"


def test_complete_workflow_updates_repository():
    repository = InMemoryWorkflowRepository()
    engine = WorkflowEngine(repository=repository)

    execution = engine.create_execution(
        make_definition(),
        execution_id="execution-001",
    )

    engine.start(execution)
    engine.start_next_step(execution)
    engine.complete_current_step(execution)

    engine.complete(execution)

    stored = repository.get("execution-001")

    assert stored is not None
    assert stored.status == WorkflowStatus.COMPLETED
    assert stored.completed_at is not None


def test_fail_current_step_updates_repository():
    repository = InMemoryWorkflowRepository()
    engine = WorkflowEngine(repository=repository)

    execution = engine.create_execution(
        make_definition(),
        execution_id="execution-001",
    )

    engine.start(execution)
    engine.start_next_step(execution)

    engine.fail_current_step(
        execution,
        error="agent failure",
    )

    stored = repository.get("execution-001")

    assert stored is not None
    assert stored.status == WorkflowStatus.FAILED
    assert stored.error == "agent failure"
    assert stored.definition.steps[0].status.value == "failed"


def test_cancel_updates_repository():
    repository = InMemoryWorkflowRepository()
    engine = WorkflowEngine(repository=repository)

    execution = engine.create_execution(
        make_definition(),
        execution_id="execution-001",
    )

    engine.cancel(execution)

    stored = repository.get("execution-001")

    assert stored is not None
    assert stored.status == WorkflowStatus.CANCELLED


def test_engine_remains_usable_without_repository():
    engine = WorkflowEngine()

    execution = engine.create_execution(
        make_definition(),
        execution_id="execution-001",
    )

    engine.start(execution)

    assert execution.status == WorkflowStatus.RUNNING
