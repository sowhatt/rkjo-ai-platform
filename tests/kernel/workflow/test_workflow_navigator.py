import pytest

from rkjo_kernel.workflow import (
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowStep,
)
from rkjo_kernel.workflow.navigator import WorkflowNavigator


def create_execution() -> WorkflowExecution:
    definition = WorkflowDefinition(
        workflow_id="navigation.workflow",
        name="Navigation workflow",
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

    execution = WorkflowExecution(definition=definition)
    execution.start()
    return execution


def test_navigator_returns_first_pending_step():
    execution = create_execution()
    navigator = WorkflowNavigator()

    step = navigator.get_next_step(execution)

    assert step is not None
    assert step.step_id == "validate"


def test_navigator_returns_second_step_after_first_completion():
    execution = create_execution()
    navigator = WorkflowNavigator()

    first_step = execution.definition.steps[0]
    first_step.start()
    first_step.complete()

    step = navigator.get_next_step(execution)

    assert step is not None
    assert step.step_id == "execute"


def test_navigator_returns_none_when_workflow_is_not_running():
    execution = create_execution()
    execution.cancel()

    navigator = WorkflowNavigator()

    assert navigator.get_next_step(execution) is None


def test_navigator_returns_previous_step():
    execution = create_execution()
    navigator = WorkflowNavigator()

    previous = navigator.get_previous_step(
        execution,
        "execute",
    )

    assert previous is not None
    assert previous.step_id == "validate"


def test_navigator_rejects_unknown_step():
    execution = create_execution()
    navigator = WorkflowNavigator()

    with pytest.raises(KeyError):
        navigator.get_previous_step(
            execution,
            "unknown",
        )
