"""Outbox contracts for reliable workflow event publication."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from rkjo_kernel.messages.agent_message import AgentMessage


@dataclass(frozen=True)
class OutboxMessage:
    """One workflow message waiting for publication."""

    outbox_id: str
    queue_name: str
    message: AgentMessage
    created_at: datetime


class OutboxStore(Protocol):
    """Persistence contract for workflow messages awaiting publication."""

    def add(
        self,
        message: OutboxMessage,
    ) -> None:
        """Persist one message for later publication."""
        ...

    def pending(
        self,
        *,
        limit: int = 100,
    ) -> list[OutboxMessage]:
        """Return unpublished messages."""
        ...

    def mark_published(
        self,
        outbox_id: str,
    ) -> None:
        """Mark one outbox message as published."""
        ...
