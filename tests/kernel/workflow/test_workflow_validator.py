import pytest

from rkjo_kernel.workflow import (
    InvalidWorkflowDefinitionError,
    InvalidWorkflowTransitionError,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowStep,
)
from rkjo_kernel.workflow.validator import WorkflowValidator


def create_step(step_id: str, position: int) -> WorkflowStep:
    return WorkflowStep(
        step_id=step_id,
        name=step_id.title(),
        agent_name=f"{step_id}_agent",
        position=position,
    )


def test_validator_rejects_empty_definition():
    validator = WorkflowValidator()
    definition = WorkflowDefinition(
        workflow_id="empty.workflow",
        name="Empty workflow",
    )

    with pytest.raises(InvalidWorkflowDefinitionError):
        validator.validate_definition(definition)


def test_validator_rejects_non_contiguous_positions():
    validator = WorkflowValidator()
    definition = WorkflowDefinition(
        workflow_id="invalid.positions",
        name="Invalid positions",
        steps=[
            create_step("validate", 0),
            create_step("execute", 2),
        ],
    )

    with pytest.raises(InvalidWorkflowDefinitionError):
        validator.validate_definition(definition)


def test_validator_accepts_contiguous_positions():
    validator = WorkflowValidator()
    definition = WorkflowDefinition(
        workflow_id="valid.workflow",
        name="Valid workflow",
        steps=[
            create_step("validate", 0),
            create_step("execute", 1),
        ],
    )

    validator.validate_definition(definition)


def test_validator_rejects_start_of_running_execution():
    validator = WorkflowValidator()
    definition = WorkflowDefinition(
        workflow_id="running.workflow",
        name="Running workflow",
        steps=[create_step("validate", 0)],
    )
    execution = WorkflowExecution(definition=definition)
    execution.start()

    with pytest.raises(InvalidWorkflowTransitionError):
        validator.validate_can_start(execution)
