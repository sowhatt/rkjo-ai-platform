from dataclasses import replace

import pytest

from rkjo_kernel.harness.checkpoint import CheckpointService
from rkjo_kernel.harness.in_memory import InMemoryHarnessStateStore
from rkjo_kernel.harness.state import HarnessState, HarnessStateStatus


def make_state(**changes):
    values = dict(
        tenant_id="tenant-a",
        mission_id="mission-1",
        trace_id="trace-1",
        status=HarnessStateStatus.RUNNING,
    )
    values.update(changes)
    return HarnessState(**values)


def test_checkpoint_increments_version_and_can_resume():
    store = InMemoryHarnessStateStore()
    service = CheckpointService(store)
    saved = service.checkpoint(make_state(data={"step": 1}))
    assert saved.checkpoint_version == 1
    assert service.resume(
        tenant_id="tenant-a", mission_id="mission-1"
    ) == saved


def test_checkpoint_rejects_stale_writer():
    store = InMemoryHarnessStateStore()
    service = CheckpointService(store)
    initial = make_state()
    service.checkpoint(initial)
    with pytest.raises(ValueError, match="Stale"):
        service.checkpoint(initial)


def test_resume_is_tenant_and_mission_scoped():
    store = InMemoryHarnessStateStore()
    service = CheckpointService(store)
    saved = service.checkpoint(make_state())
    with pytest.raises(LookupError):
        service.resume(
            tenant_id="tenant-b",
            mission_id="mission-1",
            state_id=saved.state_id,
        )
    with pytest.raises(LookupError):
        service.resume(
            tenant_id="tenant-a",
            mission_id="mission-other",
            state_id=saved.state_id,
        )


@pytest.mark.parametrize(
    "status",
    [HarnessStateStatus.COMPLETED, HarnessStateStatus.CANCELLED],
)
def test_terminal_state_cannot_resume(status):
    store = InMemoryHarnessStateStore()
    service = CheckpointService(store)
    saved = service.checkpoint(make_state(status=status))
    with pytest.raises(ValueError, match="terminal"):
        service.resume(
            tenant_id="tenant-a",
            mission_id="mission-1",
            state_id=saved.state_id,
        )


def test_failed_state_can_be_loaded_for_recovery():
    store = InMemoryHarnessStateStore()
    service = CheckpointService(store)
    saved = service.checkpoint(make_state(status=HarnessStateStatus.FAILED))
    assert service.resume(
        tenant_id="tenant-a", mission_id="mission-1"
    ).state_id == saved.state_id
