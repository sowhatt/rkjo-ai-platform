"""Thread-safe in-memory harness state store."""

from __future__ import annotations

from threading import RLock

from rkjo_kernel.harness.state import HarnessState


class InMemoryHarnessStateStore:
    def __init__(self) -> None:
        self._states: dict[str, HarnessState] = {}
        self._lock = RLock()

    def save(self, state: HarnessState) -> HarnessState:
        with self._lock:
            existing = self._states.get(state.state_id)
            if existing is not None and existing.tenant_id != state.tenant_id:
                raise ValueError(
                    "Cannot overwrite harness state across tenant boundary"
                )
            self._states[state.state_id] = state
            return state

    def get(
        self,
        state_id: str,
        *,
        tenant_id: str,
    ) -> HarnessState | None:
        self._required(tenant_id, "tenant_id")
        with self._lock:
            state = self._states.get(state_id)
            if state is None or state.tenant_id != tenant_id:
                return None
            return state

    def latest_for_mission(
        self,
        mission_id: str,
        *,
        tenant_id: str,
    ) -> HarnessState | None:
        self._required(tenant_id, "tenant_id")
        self._required(mission_id, "mission_id")
        with self._lock:
            matches = [
                state
                for state in self._states.values()
                if state.tenant_id == tenant_id
                and state.mission_id == mission_id
            ]
            if not matches:
                return None
            return max(
                matches,
                key=lambda state: (
                    state.updated_at,
                    state.checkpoint_version,
                    state.state_id,
                ),
            )

    def delete(
        self,
        state_id: str,
        *,
        tenant_id: str,
    ) -> bool:
        self._required(tenant_id, "tenant_id")
        with self._lock:
            state = self._states.get(state_id)
            if state is None or state.tenant_id != tenant_id:
                return False
            del self._states[state_id]
            return True

    @staticmethod
    def _required(value: str, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must not be empty")
        return value.strip()
