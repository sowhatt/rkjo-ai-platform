"""Mission lifecycle model.

A Mission represents *why* work exists, while WorkflowExecution represents
*how* that work is carried out. Keeping the two concepts separate lets RKJO
attach multiple workflow executions, retries and future human approvals to a
single business objective without losing its identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class MissionStatus(StrEnum):
    """Lifecycle states for a mission."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {
            MissionStatus.COMPLETED,
            MissionStatus.FAILED,
            MissionStatus.CANCELLED,
        }


@dataclass(slots=True)
class Mission:
    """Business-level objective executed by the RKJO platform."""

    objective: str
    domain: str
    mission_id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str | None = None
    user_id: str | None = None
    status: MissionStatus = MissionStatus.PENDING
    workflow_execution_ids: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        self.objective = self.objective.strip()
        self.domain = self.domain.strip().lower()
        self.mission_id = self.mission_id.strip()

        if not self.objective:
            raise ValueError("Mission objective must not be empty.")
        if not self.domain:
            raise ValueError("Mission domain must not be empty.")
        if not self.mission_id:
            raise ValueError("Mission mission_id must not be empty.")

    @property
    def is_terminal(self) -> bool:
        """Return whether the mission can no longer continue."""
        return self.status.is_terminal

    def attach_workflow(self, execution_id: str) -> None:
        """Attach a workflow execution once, preserving creation order."""
        normalized = execution_id.strip()
        if not normalized:
            raise ValueError("Workflow execution_id must not be empty.")
        if normalized not in self.workflow_execution_ids:
            self.workflow_execution_ids.append(normalized)

    def start(self) -> None:
        """Move a pending mission to running."""
        self._ensure_status({MissionStatus.PENDING}, MissionStatus.RUNNING)
        self.status = MissionStatus.RUNNING
        self.started_at = utc_now()
        self.completed_at = None
        self.error = None

    def complete(self, result: Any = None) -> None:
        """Complete a running mission and persist its final result."""
        self._ensure_status({MissionStatus.RUNNING}, MissionStatus.COMPLETED)
        self.status = MissionStatus.COMPLETED
        self.result = result
        self.error = None
        self.completed_at = utc_now()

    def fail(self, error: str) -> None:
        """Fail a running mission with an explicit reason."""
        normalized = error.strip()
        if not normalized:
            raise ValueError("A failed mission requires an error message.")
        self._ensure_status({MissionStatus.RUNNING}, MissionStatus.FAILED)
        self.status = MissionStatus.FAILED
        self.error = normalized
        self.completed_at = utc_now()

    def cancel(self) -> None:
        """Cancel a pending or running mission."""
        self._ensure_status(
            {MissionStatus.PENDING, MissionStatus.RUNNING},
            MissionStatus.CANCELLED,
        )
        self.status = MissionStatus.CANCELLED
        self.completed_at = utc_now()

    def _ensure_status(
        self,
        allowed: set[MissionStatus],
        target: MissionStatus,
    ) -> None:
        if self.status not in allowed:
            raise ValueError(
                f"Cannot move mission '{self.mission_id}' from "
                f"'{self.status.value}' to '{target.value}'."
            )
