"""In-memory transactional workflow unit of work."""

from __future__ import annotations

from copy import deepcopy

from rkjo_kernel.workflow.inbox import InboxStore
from rkjo_kernel.workflow.outbox import (
    OutboxMessage,
    OutboxStore,
)
from rkjo_kernel.workflow.repository.memory import (
    InMemoryWorkflowRepository,
)


class InMemoryInboxStore(InboxStore):
    def __init__(self) -> None:
        self._messages: set[str] = set()

    def contains(
        self,
        message_id: str,
    ) -> bool:
        return message_id in self._messages

    def mark_processed(
        self,
        message_id: str,
    ) -> None:
        self._messages.add(message_id)


class InMemoryOutboxStore(OutboxStore):
    def __init__(self) -> None:
        self._messages: dict[str, OutboxMessage] = {}
        self._published: set[str] = set()

    def add(
        self,
        message: OutboxMessage,
    ) -> None:
        self._messages[message.outbox_id] = message

    def pending(
        self,
        *,
        limit: int = 100,
    ) -> list[OutboxMessage]:
        return [
            message
            for outbox_id, message in self._messages.items()
            if outbox_id not in self._published
        ][:limit]

    def mark_published(
        self,
        outbox_id: str,
    ) -> None:
        if outbox_id not in self._messages:
            raise KeyError(
                f"Unknown outbox message '{outbox_id}'."
            )

        self._published.add(outbox_id)


class InMemoryWorkflowUnitOfWork:
    """Atomic in-memory workflow transaction."""

    def __init__(self) -> None:
        self.workflows = InMemoryWorkflowRepository()
        self.inbox = InMemoryInboxStore()
        self.outbox = InMemoryOutboxStore()

        self._snapshot = None
        self._committed = False

    def __enter__(self) -> "InMemoryWorkflowUnitOfWork":
        self._snapshot = (
            deepcopy(self.workflows),
            deepcopy(self.inbox),
            deepcopy(self.outbox),
        )
        self._committed = False
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        if exc_type is not None:
            self.rollback()
            return

        if not self._committed:
            self.rollback()

    def commit(self) -> None:
        self._committed = True

    def rollback(self) -> None:
        if self._snapshot is None:
            return

        (
            workflows_snapshot,
            inbox_snapshot,
            outbox_snapshot,
        ) = self._snapshot

        self.workflows._executions = deepcopy(
            workflows_snapshot._executions
        )
        self.inbox._messages = deepcopy(
            inbox_snapshot._messages
        )
        self.outbox._messages = deepcopy(
            outbox_snapshot._messages
        )
        self.outbox._published = deepcopy(
            outbox_snapshot._published
        )

        self._committed = False
