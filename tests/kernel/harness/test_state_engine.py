from dataclasses import replace

import pytest

from rkjo_kernel.harness import (
    HarnessState,
    HarnessStateStatus,
    InMemoryHarnessStateStore,
)


def state(**changes):
    values = {
        "tenant_id": "tenant-a",
        "mission_id": "mission-1",
        "trace_id": "trace-1",
    }
    values.update(changes)
    return HarnessState(**values)


def test_state_contract_defaults_are_safe():
    item = state()
    assert item.status is HarnessStateStatus.CREATED
    assert item.iteration == 0
    assert item.checkpoint_version == 0


def test_store_round_trip_and_latest_mission_state():
    store = InMemoryHarnessStateStore()
    first = state()
    store.save(first)
    second = replace(
        first,
        checkpoint_version=1,
        status=HarnessStateStatus.RUNNING,
    )
    store.save(second)

    assert store.get(first.state_id, tenant_id="tenant-a") == second
    assert (
        store.latest_for_mission("mission-1", tenant_id="tenant-a")
        == second
    )


def test_store_is_tenant_isolated():
    store = InMemoryHarnessStateStore()
    item = state()
    store.save(item)

    assert store.get(item.state_id, tenant_id="tenant-b") is None
    assert (
        store.latest_for_mission("mission-1", tenant_id="tenant-b")
        is None
    )
    assert not store.delete(item.state_id, tenant_id="tenant-b")


def test_store_rejects_cross_tenant_state_id_collision():
    store = InMemoryHarnessStateStore()
    original = state()
    store.save(original)

    with pytest.raises(ValueError, match="tenant boundary"):
        store.save(replace(original, tenant_id="tenant-b"))

    assert store.get(original.state_id, tenant_id="tenant-a") == original


@pytest.mark.parametrize("field", ["tenant_id", "mission_id", "trace_id"])
def test_state_requires_canonical_identity(field):
    values = {
        "tenant_id": "tenant-a",
        "mission_id": "mission-1",
        "trace_id": "trace-1",
    }
    values[field] = " "
    with pytest.raises(ValueError, match=field):
        HarnessState(**values)


def test_state_rejects_negative_versions():
    with pytest.raises(ValueError, match="iteration"):
        state(iteration=-1)
    with pytest.raises(ValueError, match="checkpoint_version"):
        state(checkpoint_version=-1)
