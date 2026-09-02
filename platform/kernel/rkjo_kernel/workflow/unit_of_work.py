"""Transactional boundary for reliable workflow processing."""

from __future__ import annotations

from typing import Protocol

from rkjo_kernel.workflow.inbox import InboxStore
from rkjo_kernel.workflow.outbox import OutboxStore
from rkjo_kernel.workflow.repository.base import WorkflowRepository


class WorkflowUnitOfWork(Protocol):
    """Atomic persistence boundary for workflow processing."""

    workflows: WorkflowRepository
    inbox: InboxStore
    outbox: OutboxStore

    def __enter__(self) -> "WorkflowUnitOfWork":
        ...

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...
