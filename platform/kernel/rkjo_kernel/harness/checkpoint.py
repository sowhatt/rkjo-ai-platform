"""Checkpoint and resume services for the durable agent harness."""

from __future__ import annotations

from dataclasses import replace

from rkjo_kernel.harness.port import HarnessStatePort
from rkjo_kernel.harness.state import HarnessState, HarnessStateStatus, utc_now


class CheckpointService:
    def __init__(self, store: HarnessStatePort) -> None:
        self.store = store

    def checkpoint(self, state: HarnessState) -> HarnessState:
        persisted = self.store.get(state.state_id, tenant_id=state.tenant_id)
        expected_version = persisted.checkpoint_version if persisted else 0
        if state.checkpoint_version != expected_version:
            raise ValueError("Stale harness state checkpoint version")
        checkpointed = replace(
            state,
            checkpoint_version=expected_version + 1,
            updated_at=utc_now(),
        )
        return self.store.save(checkpointed)

    def resume(
        self,
        *,
        tenant_id: str,
        mission_id: str,
        state_id: str | None = None,
    ) -> HarnessState:
        state = (
            self.store.get(state_id, tenant_id=tenant_id)
            if state_id is not None
            else self.store.latest_for_mission(mission_id, tenant_id=tenant_id)
        )
        if state is None or state.mission_id != mission_id:
            raise LookupError("Harness checkpoint not found")
        if state.status in {
            HarnessStateStatus.COMPLETED,
            HarnessStateStatus.CANCELLED,
        }:
            raise ValueError(
                f"Cannot resume terminal harness state '{state.status.value}'"
            )
        return state
