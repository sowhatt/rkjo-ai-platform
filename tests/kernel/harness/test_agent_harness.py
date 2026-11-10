import pytest

from rkjo_kernel.harness import CheckpointService, InMemoryHarnessStateStore
from rkjo_kernel.harness.runtime import AgentHarness, HarnessIterationResult
from rkjo_kernel.harness.state import HarnessStateStatus
from rkjo_kernel.mission.execution_context import ExecutionContext


def context(**changes):
    values = dict(
        tenant_id="tenant-a",
        mission_id="mission-1",
        trace_id="trace-1",
    )
    values.update(changes)
    return ExecutionContext(**values)


def test_harness_starts_and_checkpoints_initial_state():
    store = InMemoryHarnessStateStore()
    harness = AgentHarness(
        checkpoints=CheckpointService(store),
        executor=lambda **_: HarnessIterationResult(),
    )
    state = harness.start(context=context(), data={"goal": "analyse"})
    assert state.status is HarnessStateStatus.CREATED
    assert state.checkpoint_version == 1
    assert state.data["goal"] == "analyse"


def test_harness_iteration_checkpoints_progress_and_completion():
    store = InMemoryHarnessStateStore()
    harness = AgentHarness(
        checkpoints=CheckpointService(store),
        executor=lambda **_: HarnessIterationResult(
            output={"answer": 42},
            data={"step": "done"},
            completed=True,
        ),
    )
    initial = harness.start(context=context())
    completed = harness.run_iteration(context=context(), state=initial)

    assert completed.status is HarnessStateStatus.COMPLETED
    assert completed.iteration == 1
    assert completed.checkpoint_version == 3
    assert completed.data["step"] == "done"
    assert completed.data["last_output"] == {"answer": 42}


def test_harness_failure_is_checkpointed_before_reraising():
    store = InMemoryHarnessStateStore()

    def explode(**_):
        raise RuntimeError("boom")

    harness = AgentHarness(
        checkpoints=CheckpointService(store),
        executor=explode,
    )
    initial = harness.start(context=context())

    with pytest.raises(RuntimeError, match="boom"):
        harness.run_iteration(context=context(), state=initial)

    recovered = harness.resume(context=context())
    assert recovered.status is HarnessStateStatus.FAILED
    assert recovered.metadata["last_error_type"] == "RuntimeError"
    assert recovered.metadata["last_error"] == "boom"


def test_harness_rejects_cross_context_state_execution():
    store = InMemoryHarnessStateStore()
    harness = AgentHarness(
        checkpoints=CheckpointService(store),
        executor=lambda **_: HarnessIterationResult(),
    )
    state = harness.start(context=context())

    with pytest.raises(ValueError, match="identity"):
        harness.run_iteration(
            context=context(trace_id="other-trace"),
            state=state,
        )


def test_suspended_iteration_can_be_resumed():
    store = InMemoryHarnessStateStore()
    harness = AgentHarness(
        checkpoints=CheckpointService(store),
        executor=lambda **_: HarnessIterationResult(suspended=True),
    )
    initial = harness.start(context=context())
    suspended = harness.run_iteration(context=context(), state=initial)
    resumed = harness.resume(context=context(), state_id=suspended.state_id)

    assert suspended.status is HarnessStateStatus.SUSPENDED
    assert resumed == suspended


def test_terminal_state_cannot_execute_again():
    store = InMemoryHarnessStateStore()
    harness = AgentHarness(
        checkpoints=CheckpointService(store),
        executor=lambda **_: HarnessIterationResult(completed=True),
    )
    completed = harness.run_iteration(
        context=context(),
        state=harness.start(context=context()),
    )
    with pytest.raises(ValueError, match="terminal"):
        harness.run_iteration(context=context(), state=completed)
