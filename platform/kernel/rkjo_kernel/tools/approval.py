"""Durable HITL approval contracts for sensitive tool execution."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import Any, Protocol
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ToolApproval:
    tenant_id: str
    tool_name: str
    mission_id: str | None = None
    trace_id: str | None = None
    approval_id: str = field(default_factory=lambda: str(uuid4()))
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_by: str | None = None
    decided_by: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    decided_at: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("tenant_id", "tool_name", "approval_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"ToolApproval {name} must not be empty")
        object.__setattr__(self, "tool_name", self.tool_name.strip().lower())
        object.__setattr__(self, "metadata", deepcopy(self.metadata))


class ToolApprovalPort(Protocol):
    def save(self, approval: ToolApproval) -> ToolApproval: ...
    def get(self, approval_id: str, *, tenant_id: str) -> ToolApproval | None: ...


class InMemoryToolApprovalStore:
    def __init__(self) -> None:
        self._items: dict[str, ToolApproval] = {}
        self._lock = RLock()

    def save(self, approval: ToolApproval) -> ToolApproval:
        with self._lock:
            current = self._items.get(approval.approval_id)
            if current is not None and current.tenant_id != approval.tenant_id:
                raise ValueError("Cannot overwrite approval across tenant boundary")
            self._items[approval.approval_id] = approval
            return approval

    def get(self, approval_id: str, *, tenant_id: str) -> ToolApproval | None:
        with self._lock:
            approval = self._items.get(approval_id)
            if approval is None or approval.tenant_id != tenant_id:
                return None
            return approval


class ToolApprovalService:
    def __init__(self, store: ToolApprovalPort) -> None:
        self.store = store

    def request(
        self,
        *,
        tenant_id: str,
        tool_name: str,
        mission_id: str | None = None,
        trace_id: str | None = None,
        requested_by: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolApproval:
        return self.store.save(ToolApproval(
            tenant_id=tenant_id,
            tool_name=tool_name,
            mission_id=mission_id,
            trace_id=trace_id,
            requested_by=requested_by,
            metadata=metadata or {},
        ))

    def decide(
        self,
        *,
        approval_id: str,
        tenant_id: str,
        approved: bool,
        decided_by: str,
        reason: str | None = None,
    ) -> ToolApproval:
        current = self.store.get(approval_id, tenant_id=tenant_id)
        if current is None:
            raise LookupError("Tool approval not found")
        if current.status is not ApprovalStatus.PENDING:
            raise ValueError("Tool approval has already been decided")
        if not decided_by.strip():
            raise ValueError("decided_by must not be empty")
        return self.store.save(replace(
            current,
            status=ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED,
            decided_by=decided_by.strip(),
            reason=reason,
            decided_at=utc_now(),
        ))

    def authorize(
        self,
        *,
        approval_id: str,
        tenant_id: str,
        tool_name: str,
        mission_id: str | None,
        trace_id: str | None,
    ) -> bool:
        approval = self.store.get(approval_id, tenant_id=tenant_id)
        if approval is None or approval.status is not ApprovalStatus.APPROVED:
            return False
        return (
            approval.tool_name == tool_name.strip().lower()
            and approval.mission_id == mission_id
            and approval.trace_id == trace_id
        )
