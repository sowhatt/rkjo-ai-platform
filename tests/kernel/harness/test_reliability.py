import pytest

from rkjo_kernel.harness import CheckpointService, InMemoryHarnessStateStore
from rkjo_kernel.harness.runtime import (
    AgentHarness,
    HarnessIterationResult,
    HarnessPolicy,
)
from rkjo_kernel.harness.state import HarnessStateStatus
from rkjo_kernel.mission.execution_context import ExecutionContext
from rkjo_kernel.runtime.retry_policy import RetryPolicy


def context():
    return ExecutionContext(
        tenant_id="tenant-a",
        mission_id="mission-1",
        trace_id="trace-1",
    )


def harness(*, executor, max_iterations=100, retry_policy=None):
    return AgentHarness(
        checkpoints=CheckpointService(InMemoryHarnessStateStore()),
        executor=executor,
        policy=HarnessPolicy(max_iterations=max_iterations),
        retry_policy=retry_policy,
    )


def test_iteration_limit_is_checkpointed_as_terminal_failure():
    runtime = harness(
        executor=lambda **_: HarnessIterationResult(),
        max_iterations=1,
    )
    first = runtime.run_iteration(
        context=context(),
        state=runtime.start(context=context()),
    )
    assert first.iteration == 1

    with pytest.raises(RuntimeError, match="iteration limit"):
        runtime.run_iteration(context=context(), state=first)

    recovered = runtime.resume(context=context())
    assert recovered.status is HarnessStateStatus.FAILED
    assert recovered.metadata["termination_reason"] == "max_iterations_reached"


def test_suspend_is_durable_and_resumable():
    runtime = harness(executor=lambda **_: HarnessIterationResult())
    state = runtime.start(context=context())
    suspended = runtime.suspend(
        context=context(),
        state=state,
        reason="human_approval",
    )
    assert suspended.status is HarnessStateStatus.SUSPENDED
    assert suspended.metadata["suspension_reason"] == "human_approval"
    assert runtime.resume(context=context()) == suspended


def test_cancel_is_durable_and_terminal():
    runtime = harness(executor=lambda **_: HarnessIterationResult())
    state = runtime.start(context=context())
    cancelled = runtime.cancel(
        context=context(),
        state=state,
        reason="user_request",
    )
    assert cancelled.status is HarnessStateStatus.CANCELLED
    assert cancelled.metadata["cancellation_reason"] == "user_request"
    with pytest.raises(ValueError, match="terminal"):
        runtime.run_iteration(context=context(), state=cancelled)


def test_retry_decision_is_persisted_on_retryable_failure():
    def timeout(**_):
        raise TimeoutError("provider timeout")

    runtime = harness(
        executor=timeout,
        retry_policy=RetryPolicy(
            max_attempts=3,
            base_delay_seconds=0.25,
        ),
    )
    state = runtime.start(context=context())
    with pytest.raises(TimeoutError):
        runtime.run_iteration(context=context(), state=state)

    recovered = runtime.resume(context=context())
    assert recovered.status is HarnessStateStatus.FAILED
    assert recovered.metadata["retry_should_retry"] is True
    assert recovered.metadata["retry_attempt"] == 2
    assert recovered.metadata["retry_delay_seconds"] == 0.25
    assert recovered.metadata["retry_reason"] == "retryable_error"


def test_non_retryable_failure_is_persisted_as_permanent():
    def invalid(**_):
        raise ValueError("bad input")

    runtime = harness(
        executor=invalid,
        retry_policy=RetryPolicy(max_attempts=3),
    )
    with pytest.raises(ValueError, match="bad input"):
        runtime.run_iteration(
            context=context(),
            state=runtime.start(context=context()),
        )

    recovered = runtime.resume(context=context())
    assert recovered.metadata["retry_should_retry"] is False
    assert recovered.metadata["retry_reason"] == "permanent_error"


def test_policy_rejects_invalid_iteration_limit():
    with pytest.raises(ValueError, match="max_iterations"):
        HarnessPolicy(max_iterations=0)
