import pytest

from rkjo_kernel.workflow import (
    InvalidStepTransitionError,
    StepStatus,
    WorkflowStep,
)


def create_step():
    return WorkflowStep(
        step_id="validate",
        name="Validate request",
        agent_name="validation_agent",
        position=0,
    )


def test_step_starts_from_pending():
    step = create_step()

    step.start()

    assert step.status == StepStatus.RUNNING
    assert step.started_at is not None
    assert step.error is None


def test_step_completes_from_running():
    step = create_step()
    step.start()

    step.complete({"status": "accepted"})

    assert step.status == StepStatus.COMPLETED
    assert step.output == {"status": "accepted"}
    assert step.completed_at is not None


def test_step_fails_from_running():
    step = create_step()
    step.start()

    step.fail("Validation failed")

    assert step.status == StepStatus.FAILED
    assert step.error == "Validation failed"
    assert step.completed_at is not None


def test_pending_step_can_be_skipped():
    step = create_step()

    step.skip()

    assert step.status == StepStatus.SKIPPED
    assert step.completed_at is not None


def test_terminal_step_can_be_reset():
    step = create_step()
    step.start()
    step.complete("done")

    step.reset()

    assert step.status == StepStatus.PENDING
    assert step.output is None
    assert step.error is None
    assert step.started_at is None
    assert step.completed_at is None


def test_pending_step_cannot_complete():
    step = create_step()

    with pytest.raises(InvalidStepTransitionError):
        step.complete()


def test_running_step_cannot_start_again():
    step = create_step()
    step.start()

    with pytest.raises(InvalidStepTransitionError):
        step.start()

def test_step_can_target_agent_by_name():
    step = WorkflowStep(
        step_id="validate",
        name="Validate request",
        agent_name=" validation_agent ",
        position=0,
    )

    assert step.agent_name == "validation_agent"
    assert step.capability_name is None
    assert step.routing_mode == "agent"
    assert step.routing_target == "validation_agent"


def test_step_can_target_capability():
    step = WorkflowStep(
        step_id="risk",
        name="Analyze risk",
        capability_name=" risk.analysis ",
        position=0,
    )

    assert step.agent_name is None
    assert step.capability_name == "risk.analysis"
    assert step.routing_mode == "capability"
    assert step.routing_target == "risk.analysis"


def test_step_requires_exactly_one_routing_target():
    with pytest.raises(
        ValueError,
        match="exactly one routing target",
    ):
        WorkflowStep(
            step_id="risk",
            name="Analyze risk",
            position=0,
        )


def test_step_rejects_multiple_routing_targets():
    with pytest.raises(
        ValueError,
        match="exactly one routing target",
    ):
        WorkflowStep(
            step_id="risk",
            name="Analyze risk",
            agent_name="risk_agent",
            capability_name="risk.analysis",
            position=0,
        )


def test_step_rejects_empty_capability_name():
    with pytest.raises(
        ValueError,
        match="capability_name must be",
    ):
        WorkflowStep(
            step_id="risk",
            name="Analyze risk",
            capability_name="   ",
            position=0,
        )
