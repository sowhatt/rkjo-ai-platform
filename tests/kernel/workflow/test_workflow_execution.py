import pytest

from rkjo_kernel.workflow import (
    InvalidWorkflowTransitionError,
    StepStatus,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowStatus,
    WorkflowStep,
)


def create_execution():
    definition = WorkflowDefinition(
        workflow_id="request.processing",
        name="Request processing",
        steps=[
            WorkflowStep(
                step_id="validate",
                name="Validate request",
                agent_name="validation_agent",
                position=0,
            ),
            WorkflowStep(
                step_id="execute",
                name="Execute request",
                agent_name="execution_agent",
                position=1,
            ),
        ],
    )

    return WorkflowExecution(
        definition=definition,
        context=WorkflowContext(
            input_data={"request_id": "REQ-001"}
        ),
    )


def test_execution_starts_from_pending():
    execution = create_execution()

    execution.start()

    assert execution.status == WorkflowStatus.RUNNING
    assert execution.started_at is not None
    assert execution.is_terminal is False


def test_execution_selects_pending_step():
    execution = create_execution()
    execution.start()

    step = execution.select_step("validate")

    assert step.step_id == "validate"
    assert execution.current_step_id == "validate"
    assert execution.current_step is step


def test_execution_completes_when_all_steps_are_terminal():
    execution = create_execution()
    execution.start()

    for step in execution.definition.steps:
        execution.select_step(step.step_id)
        step.start()
        step.complete({"step": step.step_id})

    execution.complete()

    assert execution.status == WorkflowStatus.COMPLETED
    assert execution.completed_at is not None
    assert execution.current_step_id is None
    assert execution.progress() == 1.0


def test_execution_cannot_complete_with_pending_steps():
    execution = create_execution()
    execution.start()

    with pytest.raises(InvalidWorkflowTransitionError):
        execution.complete()


def test_execution_cannot_complete_with_failed_step():
    execution = create_execution()
    execution.start()

    first_step = execution.definition.steps[0]
    execution.select_step(first_step.step_id)
    first_step.start()
    first_step.fail("Agent failure")

    second_step = execution.definition.steps[1]
    second_step.skip()

    with pytest.raises(InvalidWorkflowTransitionError):
        execution.complete()


def test_execution_can_fail():
    execution = create_execution()
    execution.start()

    execution.fail("Workflow failure")

    assert execution.status == WorkflowStatus.FAILED
    assert execution.error == "Workflow failure"
    assert execution.is_terminal is True


def test_pending_execution_can_be_cancelled():
    execution = create_execution()

    execution.cancel()

    assert execution.status == WorkflowStatus.CANCELLED
    assert execution.completed_at is not None


def test_progress_reflects_terminal_steps():
    execution = create_execution()
    execution.start()

    first_step = execution.definition.steps[0]
    first_step.start()
    first_step.complete()

    assert first_step.status == StepStatus.COMPLETED
    assert execution.progress() == 0.5
