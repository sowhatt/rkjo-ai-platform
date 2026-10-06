"""Durable agent-harness state contracts."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HarnessStateStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class HarnessState:
    tenant_id: str
    mission_id: str
    trace_id: str
    state_id: str = field(default_factory=lambda: str(uuid4()))
    status: HarnessStateStatus = HarnessStateStatus.CREATED
    iteration: int = 0
    checkpoint_version: int = 0
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        for name in ("tenant_id", "mission_id", "trace_id", "state_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"HarnessState {name} must not be empty")
        if self.iteration < 0:
            raise ValueError("HarnessState iteration must be >= 0")
        if self.checkpoint_version < 0:
            raise ValueError("HarnessState checkpoint_version must be >= 0")
        object.__setattr__(self, "data", deepcopy(self.data))
        object.__setattr__(self, "metadata", deepcopy(self.metadata))
