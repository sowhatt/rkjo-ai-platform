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
