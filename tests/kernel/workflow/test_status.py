from rkjo_kernel.workflow import StepStatus, WorkflowStatus


def test_workflow_terminal_statuses():
    assert WorkflowStatus.PENDING.is_terminal is False
    assert WorkflowStatus.RUNNING.is_terminal is False
    assert WorkflowStatus.COMPLETED.is_terminal is True
    assert WorkflowStatus.FAILED.is_terminal is True
    assert WorkflowStatus.CANCELLED.is_terminal is True


def test_step_terminal_statuses():
    assert StepStatus.PENDING.is_terminal is False
    assert StepStatus.RUNNING.is_terminal is False
    assert StepStatus.COMPLETED.is_terminal is True
    assert StepStatus.FAILED.is_terminal is True
    assert StepStatus.SKIPPED.is_terminal is True
