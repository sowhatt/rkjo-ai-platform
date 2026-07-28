import pytest

from rkjo_kernel.workflow import (
    StepStatus,
    WorkflowDefinition,
    WorkflowStatus,
    WorkflowStep,
)
from rkjo_kernel.workflow.engine import WorkflowEngine


def create_definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="request.processing",
        name="Request processing",
        steps=[
            WorkflowStep(
                step_id="validate",
                name="Validate",
                agent_name="validation_agent",
                position=0,
            ),
            WorkflowStep(
                step_id="execute",
                name="Execute",
                agent_name="execution_agent",
                position=1,
            ),
        ],
    )


def test_engine_creates_isolated_execution():
    definition = create_definition()
    engine = WorkflowEngine()

    execution = engine.create_execution(
        definition,
        input_data={"request_id": "REQ-001"},
        execution_id="EXEC-001",
    )

    assert execution.execution_id == "EXEC-001"
    assert execution.definition is not definition
    assert execution.context.get("request_id") == "REQ-001"

    execution.definition.steps[0].name = "Modified"

    assert definition.steps[0].name == "Validate"


def test_engine_starts_execution():
    engine = WorkflowEngine()
    execution = engine.create_execution(
        create_definition()
    )

    engine.start(execution)

    assert execution.status == WorkflowStatus.RUNNING


def test_engine_starts_and_completes_next_step():
    engine = WorkflowEngine()
    execution = engine.create_execution(
        create_definition()
    )
    engine.start(execution)

    step = engine.start_next_step(execution)

    assert step is not None
    assert step.step_id == "validate"
    assert step.status == StepStatus.RUNNING
    assert execution.current_step is step

    engine.complete_current_step(
        execution,
        output={"valid": True},
    )

    assert step.status == StepStatus.COMPLETED
    assert execution.current_step is None
    assert execution.context.outputs["validate"] == {
        "valid": True
    }


def test_engine_executes_steps_in_order():
    engine = WorkflowEngine()
    execution = engine.create_execution(
        create_definition()
    )
    engine.start(execution)

    first_step = engine.start_next_step(execution)
    assert first_step is not None
    assert first_step.step_id == "validate"
    engine.complete_current_step(execution)

    second_step = engine.start_next_step(execution)
    assert second_step is not None
    assert second_step.step_id == "execute"
    engine.complete_current_step(execution)

    assert engine.get_next_step(execution) is None


def test_engine_completes_finished_workflow():
    engine = WorkflowEngine()
    execution = engine.create_execution(
        create_definition()
    )
    engine.start(execution)

    while engine.get_next_step(execution) is not None:
        engine.start_next_step(execution)
        engine.complete_current_step(execution)

    engine.complete(execution)

    assert execution.status == WorkflowStatus.COMPLETED
    assert execution.progress() == 1.0


def test_engine_fails_current_step_and_workflow():
    engine = WorkflowEngine()
    execution = engine.create_execution(
        create_definition()
    )
    engine.start(execution)
    step = engine.start_next_step(execution)

    engine.fail_current_step(
        execution,
        error="Agent unavailable",
    )

    assert step is not None
    assert step.status == StepStatus.FAILED
    assert execution.status == WorkflowStatus.FAILED
    assert execution.error == "Agent unavailable"


def test_engine_requires_current_step_to_complete():
    engine = WorkflowEngine()
    execution = engine.create_execution(
        create_definition()
    )
    engine.start(execution)

    with pytest.raises(
        RuntimeError,
        match="No current workflow step",
    ):
        engine.complete_current_step(execution)


def test_engine_cancels_pending_execution():
    engine = WorkflowEngine()
    execution = engine.create_execution(
        create_definition()
    )

    engine.cancel(execution)

    assert execution.status == WorkflowStatus.CANCELLED
