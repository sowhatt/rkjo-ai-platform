"""Persistence port for durable harness state."""

from __future__ import annotations

from typing import Protocol

from rkjo_kernel.harness.state import HarnessState


class HarnessStatePort(Protocol):
    def save(self, state: HarnessState) -> HarnessState: ...

    def get(
        self,
        state_id: str,
        *,
        tenant_id: str,
    ) -> HarnessState | None: ...

    def latest_for_mission(
        self,
        mission_id: str,
        *,
        tenant_id: str,
    ) -> HarnessState | None: ...

    def delete(
        self,
        state_id: str,
        *,
        tenant_id: str,
    ) -> bool: ...
